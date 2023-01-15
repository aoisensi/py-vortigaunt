from argparse import Namespace
import struct

from rich.console import Console

from typing import List

from gltflib import (
    GLTFModel,
    Mesh,
    Buffer,
    BufferView,
    BufferTarget,
    Accessor,
    ComponentType,
    AccessorType,
    Primitive,
    Node,
    Asset,
    Scene,
    Material,
)
from gltflib.gltf import GLTF
from gltflib.gltf_resource import GLBResource, FileResource

from open import open_mdl, open_vtx, open_vvd
# from srcstudiomodel import MDLFlag, MDLBone, MDLAnim

from calc import vec_max, vec_min
from type import Vector3


def convert(mdl_name: str, args: Namespace, console: Console):
    def convert_pos(pos: Vector3, scaling: bool = False) -> Vector3:
        p = (pos[0], pos[2], pos[1])
        if scaling:
            p = tuple(map(lambda x: x*args.scale, p))
        return p

    mdl = open_mdl(mdl_name)
    buffer_views = []
    accessors = []
    meshes = []
    nodes = []
    materials = []
    buffer = bytearray()
    # short_name = mdl.name.split('/')[0][:-4]

    def write_buffer(data: bytearray, target: BufferTarget) -> int:
        buffer_view = BufferView(
            buffer=0,
            byteOffset=len(buffer),
            byteLength=len(data),
            target=target.value,
        )
        buffer.extend(data)
        buffer_views.append(buffer_view)
        return len(buffer_views)-1

    if mdl.bodyparts:
        # Vertex
        def build_vertex_buffer():
            pos_max = (-99999999.0, -99999999.0, -99999999.0)
            pos_min = (+99999999.0, +99999999.0, +99999999.0)
            uv_max = (0.0, 0.0)
            uv_min = (1.0, 1.0)
            normal_max = (0.0, 0.0, 0.0)
            normal_min = (1.0, 1.0, 1.0)
            vertexes_buffer = bytearray()
            uvs_buffer = bytearray()
            normals_buffer = bytearray()
            vvd = open_vvd(mdl_name)
            vvd_vertexes = vvd.vertexes
            if vvd.fixups:
                vvd_vertexes = []
                for fixup in vvd.fixups:
                    vid = fixup.source_vertex_id
                    num = fixup.num_vertexes
                    vvd_vertexes += vvd.vertexes[vid:vid+num]
            for vvdv in vvd_vertexes:
                pos = convert_pos(vvdv.position, True)
                pos_max = vec_max(pos_max, pos)
                pos_min = vec_min(pos_min, pos)
                vertexes_buffer.extend(struct.pack('fff', *pos))

                uv = vvdv.tex_coord
                uv_max = vec_max(uv_max, uv)
                uv_min = vec_min(uv_min, uv)
                uvs_buffer.extend(struct.pack('ff', *uv))

                normal = convert_pos(vvdv.normal)
                normal_max = vec_max(normal_max, normal)
                normal_min = vec_min(normal_min, normal)
                normals_buffer.extend(struct.pack('fff', *normal))

            count = len(vvd_vertexes)
            accessors.append(Accessor(
                bufferView=write_buffer(vertexes_buffer, BufferTarget.ARRAY_BUFFER),
                componentType=ComponentType.FLOAT.value,
                type=AccessorType.VEC3.value,
                count=count,
                min=list(pos_min), max=list(pos_max),
            ))
            pos_aid = len(accessors)-1
            accessors.append(Accessor(
                bufferView=write_buffer(uvs_buffer, BufferTarget.ARRAY_BUFFER),
                componentType=ComponentType.FLOAT.value,
                type=AccessorType.VEC2.value,
                count=count,
                min=list(uv_min), max=list(uv_max),
            ))
            uv_aid = len(accessors)-1
            accessors.append(Accessor(
                bufferView=write_buffer(normals_buffer, BufferTarget.ARRAY_BUFFER),
                componentType=ComponentType.FLOAT.value,
                type=AccessorType.VEC3.value,
                count=count,
                min=list(normal_min), max=list(normal_max),
            ))
            nrml_aid = len(accessors)-1
            return (pos_aid, uv_aid, nrml_aid)
        (pos_aid, uv_aid, nrml_aid) = build_vertex_buffer()

        # Material
        for mdl_material in mdl.skins[0]:
            material_name = mdl_material.name.split('/')[-1]
            materials.append(Material(name=material_name))

        vtx = open_vtx(mdl_name)
        for mdl_bp, vtx_bp in zip(mdl.bodyparts, vtx.body_parts):
            mesh = Mesh(name=mdl_bp.name)
            primitives = []

            for mdl_model, vtx_model in zip(mdl_bp.models, vtx_bp.models):
                for mdl_mesh, vtx_mesh in zip(mdl_model.meshes, vtx_model.model_lods[0].meshes):
                    for vtx_sg in vtx_mesh.strip_groups:
                        primitive = Primitive()
                        indeces: List[int] = []
                        for vtx_strip in vtx_sg.strips:
                            for i in range(vtx_strip.num_indices // 3):
                                for j in range(3):
                                    i1 = i*3 + j + vtx_strip.index_offset
                                    i2 = vtx_sg.indices[i1]
                                    vertex = vtx_sg.vertexes[i2]
                                    i3 = vertex.orig_mesh_vert_id
                                    i4 = mdl_mesh.vertex_offset + i3
                                    index = i4 + mdl_model.vertex_index // 48

                                    indeces.append(index)

                        indeces_buffer = bytearray()
                        for index in indeces:
                            indeces_buffer.extend(struct.pack('H', index))
                        bv_id = write_buffer(indeces_buffer, BufferTarget.ELEMENT_ARRAY_BUFFER)

                        accessors.append(Accessor(
                            bufferView=bv_id,
                            componentType=ComponentType.UNSIGNED_SHORT,
                            type=AccessorType.SCALAR.value,
                            count=len(indeces),
                        ))
                        primitive.indices = len(accessors)-1
                        primitive.attributes.POSITION = pos_aid
                        primitive.attributes.TEXCOORD_0 = uv_aid
                        primitive.attributes.NORMAL = nrml_aid
                        primitive.material = mdl_mesh.material
                        primitives.append(primitive)

            mesh.primitives = primitives
            meshes.append(mesh)
            node = Node(name=mdl_bp.name, mesh=len(meshes)-1)
            nodes.append(node)

    model = GLTFModel(
        asset=Asset(generator='py-vortigaunt'),
        buffers=[Buffer(uri='buffer.bin' if args.ascii else None, byteLength=len(buffer))],
        bufferViews=buffer_views,
        accessors=accessors,
        meshes=meshes,
        nodes=nodes,
        materials=materials,
        scenes=[Scene(
            nodes=list(range(len(nodes))),
        )],
        scene=0,
    )

    export_name = mdl_name[:-4] + ('.gltf' if args.ascii else '.glb')
    if args.ascii:
        resource = FileResource('buffer.bin', data=buffer)
        gltf = GLTF(model, [resource])
        gltf.convert_to_base64_resource(resource)
        gltf.export_gltf(export_name)
    else:
        resource = GLBResource(data=buffer)
        gltf = GLTF(model, [resource])
        gltf.export_glb(export_name)
    console.print(f'Saved "{export_name}"')
