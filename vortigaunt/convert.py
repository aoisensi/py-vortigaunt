from argparse import Namespace
import math
import FbxCommon
from fbx import (
    FbxDocumentInfo,
    FbxMesh,
    FbxNode,
    FbxVector4,
    FbxVector2,
    FbxAxisSystem,
    FbxLODGroup,
    FbxDistance,
    FbxSurfaceMaterial,
    FbxSkeleton,
    FbxCluster,
    FbxSkin,
    FbxDouble3,
)
from open import _open

from typing import List

from srcstudiomodel import MDLFlag, MDLBone


def _convert(mdl_name: str, args: Namespace):
    (mdl, vtx, vvd) = _open(mdl_name)
    (manager, scene) = FbxCommon.InitializeSdkObjects()

    # scene info
    scene_info = FbxDocumentInfo.Create(manager, 'SceneInfo')
    title = mdl.name
    if title.endswith('.mdl'):
        title = title[:-4]
    title = title.split('/')[-1]
    scene_info.mTitle = title
    scene_info.mAuthor = 'py-vortigaunt'
    scene.SetSceneInfo(scene_info)
    root = scene.GetRootNode()

    # global settings
    def set_global_settings():
        settings = scene.GetGlobalSettings()
        axis = FbxAxisSystem(3, -2, 0)
        settings.SetAxisSystem(axis)
    set_global_settings()

    # Vertexes Fixup
    def fixup():
        if vvd.fixups:
            fixed = []
            for fixup in vvd.fixups:
                # lod_index = 0
                # if fixup.lod >= lod_index:
                vid = fixup.source_vertex_id
                num = fixup.num_vertexes
                fixed += vvd.vertexes[vid:vid+num]
            return fixed
        else:
            return vvd.vertexes
    fixed_vertexes = fixup()

    # Materials
    materials = []
    for mdl_material in mdl.skins[0]:
        material_name = mdl_material.name.split('/')[-1]
        material = FbxSurfaceMaterial.Create(scene, material_name)
        root.AddMaterial(material)
        materials.append(material)

    # Skeleton
    bones_node: List[FbxNode] = []

    def build_skeleton() -> List[FbxNode]:
        if mdl.flags & MDLFlag.STATIC_PROP:
            return []
        nodes: List[FbxNode] = [None] * len(mdl.bones)

        def make_bone(mdl_bone: MDLBone, nodes: List, parent_node):
            bone_node = FbxNode.Create(scene, mdl_bone.name)
            bone = FbxSkeleton.Create(scene, mdl_bone.name)
            pos = FbxDouble3(*mdl_bone.pos)
            rot = FbxDouble3(*(math.degrees(x) for x in mdl_bone.rot))
            if parent_node:  # if not root
                parent_node.AddChild(bone_node)
                bone.SetSkeletonType(2)  # eLimbNode
            bone_node.LclTranslation.Set(pos)
            bone_node.LclRotation.Set(rot)
            bone_node.SetNodeAttribute(bone)
            for mdl_cbone in mdl_bone.children:
                make_bone(mdl_cbone, nodes, bone_node)
            nodes[mdl.bones.index(mdl_bone)] = bone_node
        make_bone(mdl.root_bone, nodes, None)
        return nodes
    bones_node = build_skeleton()

    # begin convert
    for mdl_bp, vtx_bp in zip(mdl.bodyparts, vtx.body_parts):

        lod_group = FbxNode.Create(manager, f"{mdl_bp.name}_lodgroup")
        lod_group_attr = FbxLODGroup.Create(manager, '')
        lod_group.SetNodeAttribute(lod_group_attr)
        lod_thresholds = 0.0

        for lod_index in range(vtx.num_lods):
            for mdl_model, vtx_model in zip(mdl_bp.models, vtx_bp.models):
                # mdl_model_vnum = 0
                if mdl_model.num_meshes == 0:
                    continue
                vtx_model_lod = vtx_model.model_lods[lod_index]
                if vtx_model_lod.switch_point < 0.0:
                    continue
                if lod_index > 0:
                    lod_thresholds += vtx_model_lod.switch_point
                    lod_group_attr.AddThreshold(FbxDistance(lod_thresholds, ''))

                node_name = mdl_bp.name
                if lod_index > 0:
                    node_name += f"_lod{lod_index}"
                node = FbxNode.Create(manager, node_name)
                mesh = FbxMesh.Create(manager, '')

                # Create LayerElements
                smoothing = mesh.CreateElementSmoothing()
                smoothing.SetMappingMode(3)  # Polygon
                smoothing.SetReferenceMode(0)  # Direct
                smoothing_direct = smoothing.GetDirectArray()
                uv = mesh.CreateElementUV('')
                uv.SetMappingMode(2)  # PolygonVertex
                uv.SetReferenceMode(2)  # IndexToDirect
                uv_direct = uv.GetDirectArray()
                uv_index = uv.GetIndexArray()
                material = mesh.CreateElementMaterial()
                material.SetMappingMode(3)  # Polygon
                material.SetReferenceMode(2)  # IndexToDirect
                material_index = material.GetIndexArray()
                material_ii = 0

                # Material
                for i in range(root.GetMaterialCount()):
                    node.AddMaterial(root.GetMaterial(i))

                # Skeleton
                clusters = []
                if bones_node:
                    skin = FbxSkin.Create(scene, node_name)
                    for i, bone_node in enumerate(bones_node):
                        cluster = FbxCluster.Create(scene, f'{node_name}_{i}')
                        cluster.SetLinkMode(1)  # eAdditive
                        cluster.SetLink(bone_node)
                        cluster.SetAssociateModel(bone_node)
                        cluster.SetControlPointIWCount(mdl_model.num_vertices)
                        cluster.SetTransformMatrix(bone_node.EvaluateLocalTransform())
                        skin.AddCluster(cluster)
                        clusters.append(cluster)
                    mesh.AddDeformer(skin)

                # Vertexes
                mesh.InitControlPoints(len(fixed_vertexes))
                for i in range(len(fixed_vertexes)):
                    vertex = fixed_vertexes[i]
                    mesh.SetControlPointAt(
                        FbxVector4(*vertex.position),
                        FbxVector4(*vertex.normal),
                        i,
                    )
                    tex_coord = vertex.tex_coord
                    uv_direct.Add(FbxVector2(tex_coord[0], -tex_coord[1]))
                    if clusters:
                        bone_weights = vertex.bone_weights
                        for j in range(bone_weights.numbones):
                            bone_id = bone_weights.bone[j]
                            weight = bone_weights.weight[j]
                            clusters[bone_id].AddControlPointIndex(i, weight)

                node.SetNodeAttribute(mesh)

                for mdl_mesh, vtx_mesh in zip(mdl_model.meshes, vtx_model_lod.meshes):
                    for vtx_sg in vtx_mesh.strip_groups:
                        # Indices
                        for vtx_strip in vtx_sg.strips:
                            for i in range(vtx_strip.num_indices // 3):
                                for j in range(3):
                                    i1 = i*3 + [0, 2, 1][j] + vtx_strip.index_offset
                                    i2 = vtx_sg.indices[i1]
                                    vertex = vtx_sg.vertexes[i2]
                                    i3 = vertex.orig_mesh_vert_id
                                    i4 = mdl_mesh.vertex_offset + i3  # + mdl_model_vnum
                                    index = i4 + mdl_model.vertex_index // 48

                                    if j == 0:
                                        mesh.BeginPolygon()
                                    mesh.AddPolygon(index)
                                    if j == 2:
                                        mesh.EndPolygon()
                                        smoothing_direct.Add(1)
                                        material_index.SetAt(material_ii, mdl_mesh.material)
                                        material_ii += 1
                                    uv_index.Add(index)
                    # mdl_model_vnum += mdl_mesh.num_vertices
                lod_group.AddChild(node)
        root.AddChild(lod_group)

        # fbx_name = mdl_name[:-4]
        # if len(mdl.bodyparts) > 1:
        #     fbx_name += '_' + mdl_bp.name
        # fbx_name += '.fbx'
        # FbxCommon.SaveScene(manager, scene, fbx_name, pFileFormat=int(args.ascii))
        # print(f'saved "{fbx_name}"')
        # root.RemoveChild(lod_group)

    fbx_name = mdl_name[:-4] + '.fbx'
    FbxCommon.SaveScene(manager, scene, fbx_name, pFileFormat=int(args.ascii))
    print(f'saved "{fbx_name}"')
