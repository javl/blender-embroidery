import sys
import bpy

from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from pyembroidery import read

# from pyembroidery import write_png, write_svg
from math import floor
from os import path

z_height = 0.0002
scale = 10000.0
section_lift = 0.00002

NO_COMMAND = -1
STITCH = 0
JUMP = 1
TRIM = 2
STOP = 3
END = 4
COLOR_CHANGE = 5
NEEDLE_SET = 9

show_jumpwires = True


def truncate(f, n):
    return floor(f * 10**n) / 10**n


def create_material():
    """Creates a material with a color ramp based on the thread colors
    Base name of the material is ThreadMaterial, which Blender will append
    with a number if a material with this name already exists"""

    material = bpy.data.materials.new(name="ThreadMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    nodes.clear()  # Clear existing nodes

    # Nodes are created in the same order as how they are linked in the node editor
    # Add an Attribute node; we store the thread number in an attribute which this node retreives
    attribute_node = nodes.new(type="ShaderNodeAttribute")
    attribute_node.attribute_type = "OBJECT"
    attribute_node.attribute_name = "thread_index"
    attribute_node.location = (-900, 0)

    # Add a Math node; we will use this to divide the thread number by the number of thread colors to
    # find it's position in the color ramp
    math_node_divide = nodes.new(type="ShaderNodeMath")
    math_node_divide.operation = "DIVIDE"
    math_node_divide.inputs[1].default_value = len(
        thread_colors
    )  # Set the multiplier value
    math_node_divide.location = (-700, 0)

    math_node_add = nodes.new(type="ShaderNodeMath")
    math_node_add.operation = "ADD"
    math_node_add.inputs[0].default_value = 0.01  # Set the multiplier value
    math_node_add.location = (-500, 0)

    # Add a Color ramp node; this has a color for each of our threads
    color_ramp_node = nodes.new(type="ShaderNodeValToRGB")
    color_ramp_node.location = (-300, 0)
    color_ramp_node.color_ramp.interpolation = "CONSTANT"
    for index, color in enumerate(thread_colors):
        print(color)
        # use truncate to avoid floating point errors
        color_stop = color_ramp_node.color_ramp.elements.new(
            truncate(1.0 / len(thread_colors) * index, 3)
        )
        color_stop.color = (color[0], color[1], color[2], 1.0)

    # by default a color ramp has a black and white color at the start and end, remove these
    color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[0])
    color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[-1])

    # Add a Principled BSDF node
    bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf_node.location = (0, 0)

    # Add an Output node
    output_node = nodes.new(type="ShaderNodeOutputMaterial")
    output_node.location = (300, 0)

    # Connect the Attribute node to the Math node
    links.new(attribute_node.outputs["Fac"], math_node_divide.inputs[0])
    # Connect the Math node to the Color Ramp node
    links.new(math_node_divide.outputs["Value"], math_node_add.inputs[1])
    # Connect the Math node to the Color Ramp node
    links.new(math_node_add.outputs["Value"], color_ramp_node.inputs["Fac"])
    # Connect the Color Ramp node to the Base Color input of the Principled BSDF node
    links.new(color_ramp_node.outputs["Color"], bsdf_node.inputs["Base Color"])
    # Connect the Principled BSDF node to the Output node
    links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    return material


def create_line_depth_geometry_nodes(filename, material):
    nodeName = f'{filename}_GN'
    if nodeName not in bpy.data.node_groups:
        threadgeometrynodes = bpy.data.node_groups.new(type='GeometryNodeTree', name=nodeName)
    else:
        threadgeometrynodes = bpy.data.node_groups[nodeName]

    threadgeometrynodes.color_tag = 'NONE'
    threadgeometrynodes.description = ""

    threadgeometrynodes.is_modifier = True

    #threadgeometrynodes interface
    #Socket Geometry
    geometry_socket = threadgeometrynodes.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'

    #Socket Geometry
    geometry_socket_1 = threadgeometrynodes.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'


    #initialize threadgeometrynodes nodes
    #node Group Input
    group_input = threadgeometrynodes.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    #node Group Output
    group_output = threadgeometrynodes.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    #node Curve to Mesh
    curve_to_mesh = threadgeometrynodes.nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.name = "Curve to Mesh"
    #Fill Caps
    curve_to_mesh.inputs[2].default_value = False

    #node Curve Circle
    curve_circle = threadgeometrynodes.nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.name = "Curve Circle"
    curve_circle.mode = 'RADIUS'
    #Resolution
    curve_circle.inputs[0].default_value = 4
    #Radius
    curve_circle.inputs[4].default_value = 0.0002

    #node Set Material
    set_material = threadgeometrynodes.nodes.new("GeometryNodeSetMaterial")
    set_material.name = "Set Material"
    #Selection
    set_material.inputs[1].default_value = True
    if material.name in bpy.data.materials:
        set_material.inputs[2].default_value = bpy.data.materials[material.name]

    #Set locations
    group_input.location = (-360.0, 80.0)
    group_output.location = (220.0, 80.0)
    curve_to_mesh.location = (-140.0, 80.0)
    curve_circle.location = (-360.0, -20.0)
    set_material.location = (40.0, 80.0)

    #Set dimensions
    group_input.width, group_input.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    curve_to_mesh.width, curve_to_mesh.height = 140.0, 100.0
    curve_circle.width, curve_circle.height = 140.0, 100.0
    set_material.width, set_material.height = 140.0, 100.0

    #initialize threadgeometrynodes links
    #group_input.Geometry -> curve_to_mesh.Curve
    threadgeometrynodes.links.new(group_input.outputs[0], curve_to_mesh.inputs[0])
    #curve_circle.Curve -> curve_to_mesh.Profile Curve
    threadgeometrynodes.links.new(curve_circle.outputs[0], curve_to_mesh.inputs[1])
    #set_material.Geometry -> group_output.Geometry
    threadgeometrynodes.links.new(set_material.outputs[0], group_output.inputs[0])
    #curve_to_mesh.Mesh -> set_material.Geometry
    threadgeometrynodes.links.new(curve_to_mesh.outputs[0], set_material.inputs[0])
    return threadgeometrynodes


def draw_stitch(curve_data, x1, y1, x2, y2):
    """Draw a single stitch"""
    spline = curve_data.splines.new("NURBS")
    spline.points.add(4)
    spline.points[0].co = (x1, y1, 0, 1)
    spline.points[1].co = (x1, y1, z_height, 1)
    spline.points[2].co = ((x2 + x1) / 2, (y2 + y1) / 2, z_height, 1)
    spline.points[3].co = (x2, y2, z_height, 1)
    spline.points[4].co = (x2, y2, 0, 1)
    spline.use_endpoint_u = True  # do this AFTER setting the points


def parse_embroidery_data(
    context,
    filepath,
    show_jumpwires,
    do_create_material,
    line_depth,
    thread_thickness,
    create_collection,
):

    filename = ""
    report_type = "INFO"
    report_message = ""
    error_message = ""

    try:
        filename = path.basename(filepath)
        pattern = read(filepath)

        # for thread in pattern.threadlist:
        #     print(thread)
        #     print('hexcolor: ', thread.hex_color())
        #     print (thread.get_red() / 255.0, thread.get_green() / 255.0, thread.get_blue() / 255.0)
        #     print(thread.get_opaque_color())
        #     # print(dir(thread))


        # write_png(pattern, "/home/javl/test.png", {})
        # write_svg(pattern, "/home/javl/test.svg", {})
    except Exception as e:
        report_message = "Error reading file"
        report_type = "ERROR"
        return report_message, report_type

    # print(f"Number of stitches: {len(pattern.stitches)}")
    # print(f"Number of threads: {len(pattern.threadlist)}")

    if do_create_material:
        global thread_colors
        thread_colors = [
            [
                thread.get_red() / 255.0,
                thread.get_green() / 255.0,
                thread.get_blue() / 255.0,
            ]
            for thread in pattern.threadlist
        ]
        # print(thread_colors)
        # for index, thread in enumerate(pattern.threadlist):
        #     print(index, thread)

    thread_index = 0  # start at the first thread
    sections = []  # list of sections, each section is a list of stitches
    section = {"thread_index": thread_index, "stitches": [], "is_jump": False}

    for stitch in pattern.stitches:
        x = float(stitch[0]) / scale
        y = -float(stitch[1]) / scale
        c = int(stitch[2])
        # print(x, y, c)

        if c == STITCH:  # stitch and jump both draw a thread
            section["stitches"].append([x, y])

        elif c == JUMP:
            if show_jumpwires:
                section["stitches"].append([x, y])
            else:
                print("skip jump")
                sections.append(section)  # end our previous section
                section = {
                    "thread_index": thread_index,
                    "stitches": [],
                    "is_jump": True,
                }
            # sections.append(section)  # end our previous section
            # section = {"thread_index": thread_index, "stitches": [], "is_jump": True}
            # section["stitches"].append([x, y])

        elif c == COLOR_CHANGE:  # color change, move to the next thread
            sections.append(section)  # end our previous section
            thread_index += 1
            section = {"thread_index": thread_index, "stitches": [], "is_jump": False}
            # break

        elif (
            c == TRIM
        ):  # trim moves to the next section without a line between the old and new position
            sections.append(section)  # end our previous section
            section = {"thread_index": thread_index, "stitches": [], "is_jump": False}
            # section["stitches"].append([x, y])

        elif c == END:  # end of a section?
            sections.append(section)
            section = {"thread_index": thread_index, "stitches": [], "is_jump": False}

        else:  # unhandled/unknown commands
            print("Unknown command: ", c)
            sections.append(section)  # end our previous section
            section = {"thread_index": thread_index, "stitches": [], "is_jump": False}
            section["stitches"].append([x, y])

    if do_create_material:
        material = create_material()  # create our material

    # Create a new collection
    if create_collection:
        collection = bpy.data.collections.new(filename)
        bpy.context.scene.collection.children.link(collection)
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection.children[collection.name]
        )

    for index, section in enumerate(sections):  # go draw each of the sections

        bpy.ops.curve.primitive_nurbs_path_add()  # create a new curve
        curve_obj = bpy.context.object  # get the new curve object

        # for visibility we'll place each curve slightly above the previous one
        curve_obj.location.z = section_lift * index
        # We'll use a custom property to store the thread number in the curve object, this wil lbe used by the material
        curve_obj["thread_index"] = section["thread_index"]
        if do_create_material and line_depth != "GEOMETRY_NODES":  # don't aply the material if we're using geometry nodes
            curve_obj.data.materials.append( material )  # apply our material to the curve object

        curve_data = curve_obj.data  # Get the curve data
        curve_data.use_path = False
        curve_data.splines.clear()  # remove default spline
        if line_depth == "BEVEL":
            curve_data.use_fill_caps = True
            curve_data.bevel_depth = thread_thickness
            curve_data.bevel_resolution = 4
        elif line_depth == "GEOMETRY_NODES":
            GN = create_line_depth_geometry_nodes(material)
            curve_obj.modifiers.new("Geometry Nodes", "NODES")
            curve_obj.modifiers["Geometry Nodes"].node_group = GN

        # Go draw the actual stitches inside the current section
        for index, stitch in enumerate(section["stitches"]):
            if (
                index == 0
            ):  # skip the first stitch in the section, as we don't have a previous point to connect it to
                continue
            draw_stitch(
                curve_data,
                section["stitches"][index - 1][0],
                section["stitches"][index - 1][1],
                section["stitches"][index][0],
                section["stitches"][index][1],
            )

        curve_obj.data = curve_data  # Update the curve object

    bpy.ops.object.mode_set(mode="OBJECT")
    if not do_create_material:
        report_message = f"Imported {len(pattern.stitches)} stitches"
        return report_message, report_type

    report_message = f"Imported {len(pattern.stitches)} stitches with {len(pattern.threadlist)} threads"
    return report_message, report_type


class ImportEmbroideryData(Operator, ImportHelper):
    """Import embroidery data"""

    bl_idname = "import.embroidery"
    bl_label = "Import Embroidery"

    filter_glob: bpy.props.StringProperty(
        # these are all types supported by pyembroidery
        default="*.pes;*.dst;*.exp;*.jef;*.vp3;*.10o;*.100;*.bro;*.dat;*.dsb;*.dsz;*.emd;*.exy;*.fxy;*.gt;*.hus;*.inb;*.jpx;*.ksm;*.max;*.mit;*.new;*.pcd;*.pcm;*.pcq;*.pcs;*.pec;*.phb;*.phc;*.sew;*.shv;*.stc;*.stx;*.tap;*.tbf;*.u01;*.xxx;*.zhs;*.zxy;*.gcode",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    import_scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scale the imported data",
        default=10000.0,
        min=0.0001,
        max=1000.0,
        options={"HIDDEN"},
    )  # type: ignore

    thread_thickness: bpy.props.FloatProperty(
        name="Thread Thickness (mm)",
        description="Thickness of the thread in milimeters",
        default=0.2,
        min=0.01,
        max=2.00,
        options={"HIDDEN"},
    )  # type: ignore

    show_jump_wires: bpy.props.BoolProperty(
        name="Import jump wires",
        description="Include or exclude jump wires from the design",
        default=True,
        options={"HIDDEN"},
    )  # type: ignore

    do_create_material: bpy.props.BoolProperty(
        name="Create material",
        description="Create a material based on the thread information in the file",
        default=True,
        options={"HIDDEN"},
    )  # type: ignore

    create_collection: bpy.props.BoolProperty(
        name="Create a collection",
        description="Create a new collection for the created objects",
        default=True,
        options={"HIDDEN"},
    )  # type: ignore

    line_depth: bpy.props.EnumProperty(
        name="Line type",
        description="Choose what type of lines to use for the embroidery",
        items=[
            ("NO_THICKNESS", "No thickness (curve only)", "Only curves, no thickness"),
            (
                "GEOMETRY_NODES",
                "Using geometry nodes",
                "Create a geometry node setup to add thickness. Most versatile.",
            ),
            ("BEVEL", "Using bevel", "Adds thickness through the bevel property"),
        ],
        default="GEOMETRY_NODES",
        options={"HIDDEN"},
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label(text="Import Embroidery Options")
        layout.prop(self, "show_jump_wires")
        layout.prop(self, "do_create_material")
        layout.prop(self, "create_collection")
        # layout.prop(self, "clip_start")

        col = layout.column(align=True)
        col.label(text="Thickness type:")
        col.prop(self, "line_depth", expand=True)

        row = layout.row()
        row.active = self.line_depth in ["GEOMETRY_NODES", "BEVEL"]
        row.prop(self, "thread_thickness", text="Thread Thickness (mm)")

    def execute(self, context):
        thread_thickness = self.thread_thickness / 1000.0

        report_message, report_type = parse_embroidery_data(
            context,
            self.filepath,
            self.show_jump_wires,
            self.do_create_material,
            self.line_depth,
            thread_thickness,
            self.create_collection,
        )

        self.report({report_type}, report_message)
        return {"FINISHED"}


# class EMBROIDERY_PT_import_options(bpy.types.Panel):
#     bl_space_type = "FILE_BROWSER"
#     bl_region_type = "TOOL_PROPS"
#     bl_label = "Embroidery Import Options"
#     bl_parent_id = "FILE_PT_operator"

#     @classmethod
#     def poll(cls, context):
#         sfile = context.space_data
#         operator = sfile.active_operator
#         return (
#             operator.bl_idname == "IMPORT_OT_embroidery"
#             and operator.filepath.lower().endswith(".pes")
#         )

#     def draw(self, context):
#         sfile = context.space_data
#         operator = sfile.active_operator
#         layout = self.layout
#         # layout.prop(data=operator, property="csv_delimiter")
#         # layout.prop(data=operator, property="csv_leading_lines_to_discard")
#         # layout.prop(data=operator, property="csv_encoding")


classes = [
    ImportEmbroideryData,
    # EMBROIDERY_PT_import_options,
]


def menu_func_import(self, context):
    self.layout.operator(ImportEmbroideryData.bl_idname, text="Embroidery Import")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
