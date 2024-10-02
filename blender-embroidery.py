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


def draw_stitch(x1, y1, x2, y2):
    spline = curve_data.splines.new("NURBS")
    spline.points.add(4)
    spline.points[0].co = (x1, y1, 0, 1)
    spline.points[1].co = (x1, y1, z_height, 1)
    spline.points[2].co = ((x2 + x1) / 2, (y2 + y1) / 2, z_height, 1)
    spline.points[3].co = (x2, y2, z_height, 1)
    spline.points[4].co = (x2, y2, 0, 1)
    spline.use_endpoint_u = True  # do this AFTER setting the points


thread_index = 0
sections = []
section = {"thread_index": thread_index, "stitches": []}

for stitch in pattern.stitches:
    x = float(stitch[0]) / scale
    y = -float(stitch[1]) / scale
    c = int(stitch[2])

    if c == STITCH or c == JUMP:  # stitch
        # section.setdefault("stitches", []).append([x, y])
        section["stitches"].append([x, y])

    elif c == COLOR_CHANGE:  # color change
        sections.append(section)  # end our previous section
        thread_index += 1
        print("thread_index: ", thread_index)
        section = {"thread_index": thread_index, "stitches": []}
    elif c == TRIM:
        sections.append(section)  # end our previous section
        section = {"thread_index": thread_index, "stitches": []}
        section["stitches"].append([x, y])
    elif c == END:
        sections.append(section)
        section = {"thread_index": thread_index, "stitches": []}
    else:  # jumped
        print("unknown c: ", c)
        sections.append(section)  # end our previous section
        section = {"thread_index": thread_index, "stitches": []}
        section["stitches"].append([x, y])
        print("Unknown command: ", c)

material_name = "ThreadMaterial"
# material = bpy.data.materials.get(material_name)

# if material:
#     print("Material already exists, creating duplicate")

material = bpy.data.materials.new(name=material_name)
material.use_nodes = True

# Get the material's node tree
nodes = material.node_tree.nodes
links = material.node_tree.links

# Clear existing nodes
nodes.clear()

# Add a Principled BSDF node
bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
bsdf_node.location = (0, 0)

# Add an Output node
output_node = nodes.new(type="ShaderNodeOutputMaterial")
output_node.location = (300, 0)


# Add a Color ramp node
color_ramp_node = nodes.new(type="ShaderNodeValToRGB")
color_ramp_node.location = (-300, 0)

# Clear existing color stops
# color_ramp_node.color_ramp.elements.clear()
color_ramp_node.color_ramp.interpolation = "CONSTANT"

for index, color in enumerate(thread_colors):
    print(color)
    color_stop = color_ramp_node.color_ramp.elements.new(
        1.0 / len(thread_colors) * index
    )
    color_stop.color = (color[0], color[1], color[2], 1.0)

# remove the default black and white colors from the ramp
color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[0])
color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[-1])

# Connect the MixRGB node to the Base Color input of the Principled BSDF node
links.new(color_ramp_node.outputs["Color"], bsdf_node.inputs["Base Color"])

# Connect the Principled BSDF node to the Output node
links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

# Add a Math node
math_node = nodes.new(type="ShaderNodeMath")
math_node.operation = "DIVIDE"
math_node.inputs[1].default_value = len(thread_colors)  # Set the multiplier value
math_node.location = (-500, 0)

# Add an Attribute node
attribute_node = nodes.new(type="ShaderNodeAttribute")
attribute_node.attribute_type = "OBJECT"
attribute_node.attribute_name = (
    "thread_number"  # Replace with the actual attribute name
)
attribute_node.location = (-700, 0)

# Connect the Attribute node to the Math node
links.new(attribute_node.outputs["Fac"], math_node.inputs[0])

# Connect the Math node to the Color Ramp node
links.new(math_node.outputs["Value"], color_ramp_node.inputs["Fac"])

print("sections: ", len(sections))

for index, section in enumerate(sections):
    # create a curve for each sequence
    bpy.ops.curve.primitive_nurbs_path_add()
    curve_obj = bpy.context.object  # Get the newly created curve object
    # move the curve up a bit so it is slightby on top of the previous ones
    curve_obj.location.z = section_lift * index
    # store which thread number to use
    curve_obj["thread_number"] = section["thread_index"]
    curve_obj.data.materials.append(material)

    curve_data = curve_obj.data  # Get the curve data
    curve_data.splines.clear()  # remove default spline
    curve_data.use_fill_caps = True
    curve_data.bevel_depth = thread_thickness
    curve_data.bevel_resolution = 2
    # bpy.ops.wm.properties_add(data_path="object")

    for index, stitch in enumerate(section["stitches"]):
        if index == 0:
            continue
        draw_stitch(
            section["stitches"][index - 1][0],
            section["stitches"][index - 1][1],
            section["stitches"][index][0],
            section["stitches"][index][1],
        )

    curve_obj.data = curve_data  # Update the curve object
