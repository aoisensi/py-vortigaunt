from argparse import Namespace
import struct
from typing import Dict, List, Tuple

from rich.console import Console

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
    Skin,
)
from gltflib.gltf import GLTF
from gltflib.gltf_resource import GLBResource, FileResource

from srcstudiomodel import MDLFlag, MDLBone

from open import open_mdl, open_vtx, open_vvd
from calc import vec_max, vec_min
from type import Vector2, Vector3, Vector4


def convert(mdl_name: str, args: Namespace, console: Console):
    def convert_pos(pos: Vector3, scaling: bool = False) -> Vector3:
        p = (-pos[0], pos[2], pos[1])
        if scaling:
            p = tuple(map(lambda x: x*args.scale, p))
        return p

    def convert_quat(quat: Vector4) -> Vector4:
        return (-quat[0], quat[2], quat[1], quat[3])

    mdl = open_mdl(mdl_name)
    buffer_views = []
    accessors = []
    meshes = []
    nodes = []
    root = []
    materials = []
    skins = []
    buffer = bytearray()
    short_name = mdl.name.split('/')[0][:-4]

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

    # Skeleton
    skin_id = None
    bone_map: Dict[int, int] = {}
    if not mdl.flags & MDLFlag.STATIC_PROP:
        bones: List[int] = []

        def make_bone(bone: MDLBone) -> int:
            node = Node(
                name=bone.name,
                translation=list(convert_pos(bone.pos, True)),
                rotation=list(convert_quat(bone.quat)),
            )
            children = []
            for cbone in bone.children:
                children.append(make_bone(cbone))
            node.children = children if children else None
            nodes.append(node)
            id = len(nodes)-1
            bone_map[bone.id] = id
            bones.append(id)
            return id
        skeleton = make_bone(mdl.root_bone)
        root.append(skeleton)

        skins.append(Skin(
            name=short_name,
            skeleton=skeleton,
            joints=bones,
        ))
        skin_id = len(skins)-1

    if mdl.bodyparts:
        # Vertex
        vvd = open_vvd(mdl_name)
        vvd_vertexes = vvd.vertexes
        if vvd.fixups:
            vvd_vertexes = []
            for fixup in vvd.fixups:
                vid = fixup.source_vertex_id
                num = fixup.num_vertexes
                vvd_vertexes += vvd.vertexes[vid:vid+num]

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
                    if mdl_mesh.num_vertices == 0:
                        continue
                    primitive = Primitive()
                    index_map: Dict[int, int] = {}
                    positions: List[Vector3] = []
                    indeces: List[int] = []
                    texcoords: List[Vector2] = []
                    normals: List[Vector3] = []
                    weights: List[Tuple[float, float, float, float]] = []
                    joints: List[Tuple[int, int, int, int]] = []
                    pos_max = (-99999999.0, -99999999.0, -99999999.0)
                    pos_min = (+99999999.0, +99999999.0, +99999999.0)
                    for vtx_sg in vtx_mesh.strip_groups:

                        for vtx_strip in vtx_sg.strips:
                            for i in range(vtx_strip.num_indices // 3):
                                for j in [0, 2, 1]:
                                    i1 = i*3 + j + vtx_strip.index_offset
                                    i2 = vtx_sg.indices[i1]
                                    vertex = vtx_sg.vertexes[i2]
                                    i3 = vertex.orig_mesh_vert_id
                                    i4 = mdl_mesh.vertex_offset + i3
                                    vvd_index = i4 + mdl_model.vertex_index // 48

                                    if vvd_index not in index_map:
                                        vvdv = vvd_vertexes[vvd_index]
                                        index_map[vvd_index] = len(index_map)
                                        pos = convert_pos(vvdv.position, True)
                                        pos_max = vec_max(pos_max, pos)
                                        pos_min = vec_min(pos_min, pos)
                                        positions.append(pos)
                                        texcoords.append(vvdv.tex_coord)
                                        normals.append(convert_pos(vvdv.normal))

                                        # Skining
                                        if skin_id is not None:
                                            bw = vvdv.bone_weights
                                            weight = [0.0, 0.0, 0.0, 0.0]
                                            joint = [0, 0, 0, 0]
                                            for k in range(4):
                                                if k < bw.numbones:
                                                    weight[k] = bw.weight[k]
                                                    joint[k] = bone_map[bw.bone[k]]
                                            weights.append(tuple(weight))
                                            joints.append(tuple(joint))

                                    indeces.append(index_map[vvd_index])

                    # Positions
                    positions_buffer = bytearray()
                    for pos in positions:
                        positions_buffer.extend(struct.pack('fff', *pos))
                    positions_bv = write_buffer(positions_buffer, BufferTarget.ARRAY_BUFFER)
                    accessors.append(Accessor(
                        bufferView=positions_bv,
                        componentType=ComponentType.FLOAT.value,
                        type=AccessorType.VEC3.value,
                        count=len(positions),
                        max=list(pos_max),
                        min=list(pos_min),
                    ))
                    primitive.attributes.POSITION = len(accessors)-1

                    # Texcoords
                    texcoords_buffer = bytearray()
                    for uv in texcoords:
                        texcoords_buffer.extend(struct.pack('ff', *uv))
                    texcoords_bv = write_buffer(texcoords_buffer, BufferTarget.ARRAY_BUFFER)
                    accessors.append(Accessor(
                        bufferView=texcoords_bv,
                        componentType=ComponentType.FLOAT.value,
                        type=AccessorType.VEC2.value,
                        count=len(texcoords),
                    ))
                    primitive.attributes.TEXCOORD_0 = len(accessors)-1

                    # Normals
                    normals_buffer = bytearray()
                    for normal in normals:
                        normals_buffer.extend(struct.pack('fff', *normal))
                    normals_bv = write_buffer(normals_buffer, BufferTarget.ARRAY_BUFFER)
                    accessors.append(Accessor(
                        bufferView=normals_bv,
                        componentType=ComponentType.FLOAT.value,
                        type=AccessorType.VEC3.value,
                        count=len(normals),
                    ))
                    primitive.attributes.NORMAL = len(accessors)-1

                    # Indeces
                    indeces_buffer = bytearray()
                    for index in indeces:
                        indeces_buffer.extend(struct.pack('H', index))
                    indeces_bv = write_buffer(indeces_buffer, BufferTarget.ELEMENT_ARRAY_BUFFER)
                    accessors.append(Accessor(
                        bufferView=indeces_bv,
                        componentType=ComponentType.UNSIGNED_SHORT.value,
                        type=AccessorType.SCALAR.value,
                        count=len(indeces),
                    ))
                    primitive.indices = len(accessors)-1

                    if skin_id is not None:
                        # Weigths
                        weights_buffer = bytearray()
                        for weight in weights:
                            weights_buffer.extend(struct.pack('ffff', *weight))
                        weights_bv = write_buffer(weights_buffer, BufferTarget.ELEMENT_ARRAY_BUFFER)
                        accessors.append(Accessor(
                            bufferView=weights_bv,
                            componentType=ComponentType.FLOAT.value,
                            type=AccessorType.VEC4.value,
                            count=len(weights),
                        ))
                        primitive.attributes.WEIGHTS_0 = len(accessors)-1

                        # Joints
                        joints_buffer = bytearray()
                        for joint in joints:
                            joints_buffer.extend(struct.pack('BBBB', *joint))
                        joints_bv = write_buffer(joints_buffer, BufferTarget.ARRAY_BUFFER)
                        accessors.append(Accessor(
                            bufferView=joints_bv,
                            componentType=ComponentType.UNSIGNED_BYTE.value,
                            type=AccessorType.VEC4.value,
                            count=len(joints),
                        ))
                        primitive.attributes.JOINTS_0 = len(accessors)-1

                    # Material
                    primitive.material = mdl_mesh.material
                    if skin_id is not None:
                        # Weights
                        weights_buffer = bytearray()
                        for weight in weights:
                            weights_buffer.extend(struct.pack('ffff', *weight))
                        wbv_id = write_buffer(weights_buffer, BufferTarget.ARRAY_BUFFER)

                        accessors.append(Accessor(
                            bufferView=wbv_id,
                            componentType=ComponentType.FLOAT,
                            type=AccessorType.VEC4.value,
                            count=len(weights),
                        ))

                        primitive.attributes.WEIGHTS_0 = len(accessors)-1

                        # Joints
                        joints_buffer = bytearray()
                        for joint in joints:
                            joints_buffer.extend(struct.pack('BBBB', *joint))
                        jbv_id = write_buffer(joints_buffer, BufferTarget.ARRAY_BUFFER)

                        accessors.append(Accessor(
                            bufferView=jbv_id,
                            componentType=ComponentType.UNSIGNED_BYTE,
                            type=AccessorType.VEC4.value,
                            count=len(joints),
                        ))
                        primitive.attributes.JOINTS_0 = len(accessors)-1
                    primitives.append(primitive)

            mesh.primitives = primitives
            meshes.append(mesh)
            node = Node(name=mdl_bp.name, mesh=len(meshes)-1, skin=skin_id)
            nodes.append(node)
            root.append(len(nodes)-1)

    model = GLTFModel(
        asset=Asset(generator='py-vortigaunt'),
        buffers=[Buffer(uri='buffer.bin' if args.ascii else None, byteLength=len(buffer))],
        bufferViews=buffer_views,
        accessors=accessors,
        meshes=meshes,
        nodes=nodes,
        materials=materials,
        skins=skins,
        scenes=[Scene(nodes=root)],
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
