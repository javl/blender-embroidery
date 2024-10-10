import sys
import bpy  # importing late so we can run this script from VS code as well

sys.path.append(
    "/home/javl/Documents/projects/blender-embroidery/venv/lib/python3.10/site-packages"
)
from pyembroidery import read

file_path = "/home/javl/Documents/projects/blender-embroidery/sample1.pes"
# file_path = "/home/javl/Documents/projects/blender-embroidery/logo_edited.pes"
# file_path = "/home/javl/Documents/projects/blender-embroidery/dogfre3_120.pes"
# file_path = '/home/javl/Documents/projects/blender-embroidery/balletfree26_100.pes'
# file_path = '/home/javl/Documents/projects/blender-embroidery/wpooho32_100.pes'
pattern = read(file_path)

print(f"Number of stitches: {len(pattern.stitches)}")
print(f"Number of threads: {len(pattern.threadlist)}")

thread_colors = [
    [thread.get_red() / 255.0, thread.get_green() / 255.0, thread.get_blue() / 255.0]
    for thread in pattern.threadlist
]

z_height = 0.0002
scale = 10000.0
thread_thickness = 0.0002
section_lift = 0.00002

NO_COMMAND = -1
STITCH = 0
JUMP = 1
TRIM = 2
STOP = 3
END = 4
COLOR_CHANGE = 5
NEEDLE_SET = 9

def create_material():
    """ Creates a material with a color ramp based on the thread colors
    Base name of the material is ThreadMaterial, which Blender will append
    with a number if a material with this name already exists """

    material = bpy.data.materials.new(name="ThreadMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    nodes.clear() # Clear existing nodes

    # Nodes are created in the same order as they are linked in the node editor

    # Add an Attribute node; we store the thread number in an attribute which this node retreives
    attribute_node = nodes.new(type="ShaderNodeAttribute")
    attribute_node.attribute_type = "OBJECT"
    attribute_node.attribute_name = ( "thread_number" )
    attribute_node.location = (-700, 0)

    # Add a Math node; we will use this to divide the thread number by the number of thread colors to
    # find it's position in the color ramp
    math_node = nodes.new(type="ShaderNodeMath")
    math_node.operation = "DIVIDE"
    math_node.inputs[1].default_value = len(thread_colors)  # Set the multiplier value
    math_node.location = (-500, 0)

    # Add a Color ramp node; this has a color for each of our threads
    color_ramp_node = nodes.new(type="ShaderNodeValToRGB")
    color_ramp_node.location = (-300, 0)
    color_ramp_node.color_ramp.interpolation = "CONSTANT"
    for index, color in enumerate(thread_colors):
        print(color)
        color_stop = color_ramp_node.color_ramp.elements.new(
            1.0 / len(thread_colors) * index
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
    links.new(attribute_node.outputs["Fac"], math_node.inputs[0])
    # Connect the Math node to the Color Ramp node
    links.new(math_node.outputs["Value"], color_ramp_node.inputs["Fac"])
    # Connect the Color Ramp node to the Base Color input of the Principled BSDF node
    links.new(color_ramp_node.outputs["Color"], bsdf_node.inputs["Base Color"])
    # Connect the Principled BSDF node to the Output node
    links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    return material

def draw_stitch(curve_data, x1, y1, x2, y2):
    """ Draw a single stitch """
    spline = curve_data.splines.new("NURBS")
    spline.points.add(4)
    spline.points[0].co = (x1, y1, 0, 1)
    spline.points[1].co = (x1, y1, z_height, 1)
    spline.points[2].co = ((x2 + x1) / 2, (y2 + y1) / 2, z_height, 1)
    spline.points[3].co = (x2, y2, z_height, 1)
    spline.points[4].co = (x2, y2, 0, 1)
    spline.use_endpoint_u = True  # do this AFTER setting the points

def parse_pattern():
    thread_index = 0  # start at the first thread
    sections = [] # list of sections, each section is a list of stitches
    section = {"thread_index": thread_index, "stitches": []}

    for stitch in pattern.stitches:
        x = float(stitch[0]) / scale
        y = -float(stitch[1]) / scale
        c = int(stitch[2])

        if c == STITCH or c == JUMP:  # stitch and jump both draw a thread
            section["stitches"].append([x, y])

        elif c == COLOR_CHANGE:  # color change, move to the next thread
            sections.append(section)  # end our previous section
            thread_index += 1
            section = {"thread_index": thread_index, "stitches": []}

        elif c == TRIM:  # trim moves to the next section without a line between the old and new position
            sections.append(section)  # end our previous section
            section = {"thread_index": thread_index, "stitches": []}
            # section["stitches"].append([x, y])

        elif c == END:  # end of a section?
            sections.append(section)
            section = {"thread_index": thread_index, "stitches": []}

        else: # unhandled/unknown commands
            print("Unknown command: ", c)
            sections.append(section)  # end our previous section
            section = {"thread_index": thread_index, "stitches": []}
            section["stitches"].append([x, y])

    material = create_material()  # create our material

    for index, section in enumerate(sections):  # go draw each of the sections

        bpy.ops.curve.primitive_nurbs_path_add()  # create a new curve
        curve_obj = bpy.context.object  # get the new curve object
        # for visibility we'll place each curve slightly above the previous one
        curve_obj.location.z = section_lift * index
        # We'll use a custom property to store the thread number in the curve object, this wil lbe used by the material
        curve_obj["thread_number"] = section["thread_index"]
        curve_obj.data.materials.append(material)  # apply our material to the curve object

        curve_data = curve_obj.data  # Get the curve data
        curve_data.splines.clear()  # remove default spline
        curve_data.use_fill_caps = True
        curve_data.bevel_depth = thread_thickness
        curve_data.bevel_resolution = 4

        # Go draw the actual stitches inside the current section
        for index, stitch in enumerate(section["stitches"]):
            if index == 0:
                # skip the first stitch in the section, as we don't have a previous point to connect it to
                continue
            draw_stitch(
                curve_data,
                section["stitches"][index - 1][0],
                section["stitches"][index - 1][1],
                section["stitches"][index][0],
                section["stitches"][index][1],
            )

        curve_obj.data = curve_data  # Update the curve object

    bpy.ops.object.mode_set(mode='OBJECT')

parse_pattern()
