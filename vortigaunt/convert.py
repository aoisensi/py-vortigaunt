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
    FbxAnimStack,
    FbxAnimLayer,
    FbxTime,
    FbxQuaternion,
    FbxPose,
    FbxMatrix,
)
from open import _open

from typing import Dict, List

from srcstudiomodel import MDLFlag, MDLBone, MDLAnim


def _convert(mdl_name: str, args: Namespace):
    (mdl, vtx, vvd) = _open(mdl_name)
    unexported_anims = True

    # begin convert
    bp_range = list(range(len(mdl.bodyparts)))
    if not bp_range:
        bp_range = [None]
    for bp_id in bp_range:
        mdl_bp = mdl.bodyparts[bp_id] if bp_id is not None else None
        vtx_bp = vtx.body_parts[bp_id] if bp_id is not None and vtx else None

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
            if not vvd:
                return []
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

            pose = FbxPose.Create(scene, 'bind_pose')
            pose.SetIsBindPose(True)

            def make_bone(mdl_bone: MDLBone, nodes: List, parent_node):
                bone_node = FbxNode.Create(scene, mdl_bone.name)
                bone = FbxSkeleton.Create(scene, mdl_bone.name)
                pos = FbxDouble3(*mdl_bone.pos)
                rot = FbxDouble3(*(math.degrees(x) for x in mdl_bone.rot))
                if parent_node:  # if not root
                    parent_node.AddChild(bone_node)
                    bone.SetSkeletonType(2)  # eLimbNode
                # else:
                #     root.AddChild(bone_node)
                bone_node.LclTranslation.Set(pos)
                bone_node.LclRotation.Set(rot)
                bone_node.SetNodeAttribute(bone)
                pose.Add(bone_node, FbxMatrix(bone_node.EvaluateGlobalTransform()))
                for mdl_cbone in mdl_bone.children:
                    make_bone(mdl_cbone, nodes, bone_node)
                nodes[mdl.bones.index(mdl_bone)] = bone_node
            make_bone(mdl.root_bone, nodes, None)
            # pose.Add(root, FbxMatrix())
            return nodes
        bones_node = build_skeleton()

        # Animations
        if unexported_anims and bones_node:
            for mdl_sd in mdl.seq_descs:
                def flatten_anims(anims: Dict[int, MDLAnim], anim: MDLAnim) -> Dict[int, MDLAnim]:
                    anims[anim.bone] = anim
                    if anim.next:
                        return flatten_anims(anims, anim.next)
                    else:
                        return anims
                    # if mdl_sd.label == 'ref':  # bind pose
                    #     pose = FbxPose.Create(scene, 'ref')
                    #     pose.SetIsBindPose(True)
                    #     mdl_ad = mdl.anim_descs[mdl_sd.anims[0][0]]
                    #     mdl_anims = flatten_anims({}, mdl_ad.anims[0])

                    #     for bone_id in mdl_anims:
                    #         mdl_anim = mdl_anims[bone_id]
                    #         node = bones_node[bone_id]
                    #         if mdl_anim.raw_pos:
                    #             node.LclTranslation.Set(FbxDouble3(*mdl_anim.raw_pos))
                    #         # if mdl_anim.raw_rot:
                    #         #     node.LclRotation.Reset()
                    #         #     node.LclRotation.Set(FbxQuaternion(*mdl_anim.raw_rot))
                    #     for node in bones_node:
                    #         pose.Add(node, FbxMatrix(node.EvaluateGlobalTransform()))

                    # def apply_bone_pose(bone: MDLBone, matrix: FbxMatrix):
                    #     node = bones_node[bone.id]
                    #     if bone.id in mdl_anims:
                    #         anim = mdl_anims[bone.id]
                    #         pos = FbxVector4(*anim.raw_pos) if anim.raw_pos else FbxVector4()
                    #         rot = FbxQuaternion(*anim.raw_rot) if anim.raw_rot else FbxQuaternion()
                    #         scl = FbxVector4(1.0, 1.0, 1.0)
                    #         matrix *= FbxMatrix(pos, rot, scl)
                    #     else:
                    #         matrix *= FbxMatrix(
                    #             FbxVector4(*bone.pos),
                    #             FbxVector4(), #FbxQuaternion(*bone.quat),
                    #             FbxVector4(1.0, 1.0, 1.0),
                    #         )
                    #     pose.Add(node, matrix)
                    #     for cbone in bone.children:
                    #         apply_bone_pose(cbone, matrix)
                    # apply_bone_pose(mdl.root_bone, FbxMatrix())

                    # for bone in range(len(bones_node)):
                    #     node = bones_node[bone]
                    #     if bone in mdl_anims:
                    #         anim = mdl_anims[bone]
                    #         pos = FbxVector4(*anim.raw_pos) if anim.raw_pos else FbxVector4()
                    #         rot = FbxQuaternion(*anim.raw_rot) if anim.raw_rot else FbxQuaternion()
                    #         scl = FbxVector4(1.0, 1.0, 1.0)
                    #         # node.LclTransform
                    #         matrix = FbxMatrix(pos, rot, scl)
                    #         pose.Add(node, matrix)
                    #     else:
                    #         matrix = FbxMatrix(node.EvaluateLocalTransform())
                    #         pose.Add(node, matrix)
                    # continue  # end of bind pose

                if len(mdl_sd.anims) == 1 and len(mdl_sd.anims[0]) == 1:
                    # Simple Animation
                    anim_stack = FbxAnimStack.Create(scene, mdl_sd.label)
                    mdl_ad = mdl.anim_descs[mdl_sd.anims[0][0]]
                    if not mdl_ad.anims:
                        continue
                    time = FbxTime()
                    anim_layer = FbxAnimLayer.Create(scene, mdl_ad.name)
                    anim_stack.AddMember(anim_layer)
                    print(mdl_ad.name)

                    def create_curve(mdl_anim: MDLAnim):
                        print(mdl_anim.bone)
                        bone_node = bones_node[mdl_anim.bone]
                        for axis, channel in enumerate(['X', 'Y', 'Z']):
                            curve_pos = bone_node.LclTranslation.GetCurve(anim_layer, channel, True)
                            curve_rot = bone_node.LclRotation.GetCurve(anim_layer, channel, True)
                            if mdl_anim.raw_pos:
                                curve_pos.KeyModifyBegin()
                                key_index = curve_pos.KeyAdd(time)[0]
                                curve_pos.KeySetValue(key_index, mdl_anim.raw_pos[axis])
                                curve_pos.KeyModifyEnd()
                            if mdl_anim.raw_rot:
                                rot = FbxQuaternion(*mdl_anim.raw_rot).DecomposeSphericalXYZ()
                                curve_rot.KeyModifyBegin()
                                key_index = curve_rot.KeyAdd(time)[0]
                                curve_rot.KeySetValue(key_index, rot[axis])
                                curve_rot.KeyModifyEnd()

                    create_curve(mdl_ad.anims[0])
            unexported_anims = False

        if vtx and vtx_bp and mdl_bp:
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

        fbx_name = mdl_name[:-4]
        if len(mdl.bodyparts) > 1:
            if mdl_bp and fbx_name.split('/')[-1] != mdl_bp.name:
                fbx_name += '_' + mdl_bp.name
        fbx_name += '.fbx'
        FbxCommon.SaveScene(manager, scene, fbx_name, pFileFormat=int(args.ascii))
        print(f'Saved "{fbx_name}"')
