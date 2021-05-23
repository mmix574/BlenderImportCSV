# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import bpy
import csv
import mathutils
from collections import OrderedDict
from bpy_extras.io_utils import axis_conversion
from bpy.props import BoolProperty, StringProperty, EnumProperty
import math

bl_info = {
    "name": "PIX CSV",
    "author": "Stanislav Bobovych",
    "version": (2, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "description": "Import PIX CSV dump of mesh. Imports mesh, normals and UVs.",
    "category": "Import"}


class PIX_CSV_Operator(bpy.types.Operator):

    # Plugin definitions, such as ID, name, and file extension filters
    bl_idname = "object.pix_csv_importer"
    bl_label = "Import PIX CSV"
    filepath = StringProperty(subtype = "FILE_PATH")
    filter_glob = StringProperty(default = "*.csv", options = {'HIDDEN'})

    # Options for generation of vertices
    mirror_x = BoolProperty(
                            name = "Mirror X",
                            description = "Mirror all the vertices across X axis",
                            default = True,
                            )

    vertex_order = BoolProperty(
                                name = "Change vertex order",
                                description = "Reorder vertices in counter-clockwise order",
                                default = True,
                                )

    # Options for axis alignment
    axis_forward = EnumProperty(
                                name = "Forward",
                                items = (
                                         ('X', "X Forward", ""),
                                         ('Y', "Y Forward", ""),
                                         ('Z', "Z Forward", ""),
                                         ('-X', "-X Forward", ""),
                                         ('-Y', "-Y Forward", ""),
                                         ('-Z', "-Z Forward", ""),
                                         ),
                                default = 'Z',
                                )

    axis_up = EnumProperty(
                           name = "Up",
                           items = (
                                    ('X', "X Up", ""),
                                    ('Y', "Y Up", ""),
                                    ('Z', "Z Up", ""),
                                    ('-X', "-X Up", ""),
                                    ('-Y', "-Y Up", ""),
                                    ('-Z', "-Z Up", ""),
                                    ),
                           default = 'Y',
                           )


# ~~~~~~~~~~~~~~~~~~~~Operator Functions~~~~~~~~~~~~~~~~~~~~
    def execute(self, context):
        keywords = self.as_keywords(ignore = ("axis_forward", "axis_up", "filter_glob"))
        global_matrix = axis_conversion(from_forward = self.axis_forward, from_up = self.axis_up).to_4x4()

        keywords["global_matrix"] = global_matrix
        #print(keywords)
        importCSV(**keywords)

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text = "Import Options")

        row = col.row()
        row.prop(self, "mirror_x")
        row = col.row()
        row.prop(self, "vertex_order")
        layout.prop(self, "axis_forward")
        layout.prop(self, "axis_up")


# ~~~~~~~~~~~~~~~~~~~~Mesh-Related Functions~~~~~~~~~~~~~~~~~~~~
def make_mesh(vertices, faces, normals, uvs, global_matrix):

    # Create a new mesh from the vertices and faces
    mesh = bpy.data.meshes.new('name')
    mesh.from_pydata(vertices, [], faces)

    # Generate normals
    index = 0
    for vertex in mesh.vertices:
        vertex.normal = normals[index]
        index += 1

    # Generate UV data
    uv_layer = mesh.uv_layers.new(name = "UV")
    for face, uv in enumerate(uv_layer.data): uv.uv = uvs[face]

    mesh.update(calc_edges = False)

    obj = bpy.data.objects.new('name', mesh)    # Create the mesh object for the imported mesh
    obj.matrix_world = global_matrix            # Apply transformation matrix
    bpy.context.collection.objects.link(obj)    # Link object to scene


def importCSV(filepath = None, mirror_x = False, vertex_order = True, global_matrix = None):

    # Translates coordinates of things to the global space by ensuring that there's a global matrix to use
    if global_matrix is None: global_matrix = mathutils.Matrix()

    # Check if a valid filepath was given; if nothing was given, cancel the import
    if filepath == None: return

    # Dictionaries
    vertex_dict = {}
    normal_dict = {}

    # Arrays/Lists
    vertices = []
    faces = []
    normals = []
    uvs = []


    headers = [c.strip() for c in  open(filepath).readline().strip().split(',')]
    
    
    uv_coord_name = ['in_TEXCOORD0.x','texcoord0.x']
    
    uv0_x = -1
    uv0_y = -1
    
    if('in_TEXCOORD0.x' in headers):
        uv0_x = headers.index('in_TEXCOORD0.x')
        uv0_y = headers.index('in_TEXCOORD0.y')

    if('texcoord0.x' in headers):
        uv0_x = headers.index('texcoord0.x')
        uv0_y = headers.index('texcoord0.y')
    
    if(uv0_x <0 or uv0_y<0 ):
        raise Exception('do not found uv coordinate')
    
    
    contailNormal = False
    if('in_NORMAL0.x' in headers):
        normal0_x = headers.index('in_NORMAL0.x')
        normal0_y = headers.index('in_NORMAL0.y')
        normal0_z = headers.index('in_NORMAL0.z')
    
        contailNormal = normal0_x>-1 and normal0_y>-1 and normal0_z>-1
    
    with open(filepath) as f:

        # Create the CSV reader
        reader = csv.reader(f) # Initialize the reader
        next(reader)  # Skip the CSV header

        #face_count = sum(1 for row in reader) / 3
        #print(face_count)

        #f.seek(0)
        #reader = csv.reader(f)
        #next(reader)  # skip header

        # Check if user wants vertices to be mirrored on the X-axis
        if mirror_x: x_mod = -1
        else: x_mod = 1

        # For-Loop variables
        i = 0
        current_face = []

        for row in reader:

            vertex_index = int(row[0])

            # X, Y, Z coordinates of vertices
            vertex_dict[vertex_index] = (
                                         x_mod * float(row[2]), # X
                                                 float(row[4]), # Y
                                                 float(row[3]), # Z
                                         )
            if(contailNormal):
                normal_x = float(row[normal0_x])
                normal_y = float(row[normal0_y])
                normal_z = float(row[normal0_z])
        
            
                normal_dict[vertex_index] = (
                                             normal_x, # X
                                             normal_y, # Y
                                             normal_z, # Z
                                             )
            else:
                normal_dict[vertex_index] = (0,0,0)

            #Add support for changing the origin of UV coords
            uv = (float(row[uv0_x]), float(row[uv0_y])) # X and Y coordinates while also modifying V

            if i < 2:
                # Append "current" data to list/array until a 3-vertex face is formed
                current_face.append(vertex_index)
                uvs.append(uv)
                i += 1
            else:
                # Append face and UV data to appropriate dictionary/array/list
                current_face.append(vertex_index)
                #TODO: Add option to change order of marching vertices
                if vertex_order: faces.append((current_face[0], current_face[1], current_face[2]))
                else: faces.append(current_face)
                uvs.append(uv)

                # Clear For-Loop variables for next iteration
                current_face = []
                i = 0

        # Zero out any missing vertices/normals
        for i in range(len(vertex_dict)):
            if i in vertex_dict:
                pass
            else:
                #print("missing",i)
                vertex_dict[i] = (0, 0, 0)
                normal_dict[i] = (0, 0, 0)

        # Dictionary sorted by key
        vertex_dict = OrderedDict(sorted(vertex_dict.items(), key=lambda t: t[0]))
        normal_dict = OrderedDict(sorted(normal_dict.items(), key=lambda t: t[0]))

        for key in vertex_dict: vertices.append(list(vertex_dict[key]))
        #print(key,vertex_dict[key])
        for key in normal_dict: normals.append(list(normal_dict[key]))

        #print(vertices)
        #print(faces)
        #print(normals)
        #print(uvs)
        make_mesh(vertices, faces, normals, uvs, global_matrix)


# ~~~~~~~~~~~~~~~~~~~~Registration Functions~~~~~~~~~~~~~~~~~~~~
classes = (PIX_CSV_Operator,)

def menu_func_import(self, context):
    self.layout.operator(PIX_CSV_Operator.bl_idname, text="PIX CSV (.csv)")

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


# ~~~~~~~~~~~~~~~~~~~~MAIN Block~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    #register()                                             # Uncomment this to run as a plugin
    #These run the script from "Run script" button
    bpy.utils.register_class(PIX_CSV_Operator)              # Comment this to run as a plugin
    bpy.ops.object.pix_csv_importer('INVOKE_DEFAULT')       # Comment this to run as a plugin
