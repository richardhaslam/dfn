import attr
from typing import Union
import numpy as np
from gmsh_api import gmsh
from gmsh_api import options
from gmsh_api import field
from fracture import FractureShape

import gmsh as raw_gmsh

"""
Script for creation of a parametrized EGS model with fixed set of fractures.

TODO:

- class for statistic fracture data
- full class for single generated fracture
- random fractures in the cube (use SKB)
- random fields
- flow123d on random fractures

- separate all fractures into coarse and fine mesh
- for every fine fracture get intersected elements in the coarse mesh
possible ways:
    - get bounding box for a fracture gmsh.model.getBoundingBox, 
      find elements in the box
    - try to add coarse mesh into a model using addDiscreteEntity
    - load fine fractures into flow123d, marked as boundary or 'tool region' (double dots)
      use tool fractures to identify elements (similar to rivers (1d intersectiong 2d)
      use field that depends on intersection surface and fracture properties
"""









def generate_mesh():
    r""" Create mesh and write it to a file.

    Parameters
    ----------
    fractures_data : list of FractureData
      Array of objects defining fractures.
    max_el_size : double
      Maximal size of mesh element.
    file_name : str
      File name to write mesh into.
    verbose : {0, 1}
      If set to 1, messages during mesh generation will be printed.
    """

    # geometry prameters
    box_size = 600
    well_radius = 3
    well_length = 300
    well_shift = 100



    factory = gmsh.GeometryOCC("three_frac_symmetric", verbose=True)
    gopt = options.Geometry()
    gopt.Tolerance = 1e-5
    gopt.ToleranceBoolean = 1e-3
    # gopt.MatchMeshTolerance = 1e-1

    # Main box
    box = factory.box(3 * [box_size]).set_region("box")
    side = factory.rectangle(2 * [box_size])
    side_z0 = side.copy().translate([0, 0, -box_size / 2])
    side_z1 = side.copy().translate([0, 0, +box_size / 2])
    sides = dict(
        side_z0 = side.copy().translate([0, 0, -box_size / 2]),
        side_z1 = side.copy().translate([0, 0, +box_size / 2]),
        side_y0 = side_z0.copy().rotate([-1, 0, 0], np.pi / 2),
        side_y1 = side_z1.copy().rotate([-1, 0, 0], np.pi / 2),
        side_x0 = side_z0.copy().rotate([0, 1, 0], np.pi / 2),
        side_x1 = side_z1.copy().rotate([0, 1, 0], np.pi / 2)
    )
    for name, side in sides.items():
        side.modify_regions(name)

    b_box = box.get_boundary().copy()

    # two vertical cut-off wells, just permeable part
    well_z_shift = -well_length/2
    left_center =  [-well_shift, 0, 0]
    right_center = [+well_shift, 0, 0]
    left_well = factory.cylinder(well_radius, axis=[0, 0, well_length])\
                    .translate([0,0,well_z_shift]).translate(left_center)
    right_well = factory.cylinder(well_radius, axis=[0, 0, well_length])\
                    .translate([0, 0, well_z_shift]).translate(right_center)

    left_center =  [-0.6*well_shift, 0, 0]
    right_center = [+0.6*well_shift, 0, 0]

    b_right_well = right_well.get_boundary()
    b_left_well = left_well.get_boundary()

    # fracutres
    fractures = [
        FractureShape(r, centre, axis, angle, region) for r, centre, axis, angle, region in
        [
            (1.5 * well_shift, left_center,  [0, 1, 0], np.pi/6, 'left_fr'),
            (1.5 * well_shift, right_center, [0, 1, 0], np.pi/6, 'right_fr'),
            (well_shift, [0,0,0],      [0, 1, 0], -np.pi/3, 'center_fr')
        ]]
    fractures = factory.make_fractures(fractures, factory.rectangle())
    fractures_group = factory.group(*fractures)

    # drilled box and its boundary
    box_drilled = box.cut(left_well, right_well)

    # fractures, fragmented, fractures boundary
    fractures_group = fractures_group.intersect(box_drilled.copy())
    box_fr, fractures_fr = factory.fragment(box_drilled, fractures_group)
    b_box_fr = box_fr.get_boundary()
    b_left_r = b_box_fr.select_by_intersect(b_left_well).set_region(".left_well")
    b_right_r = b_box_fr.select_by_intersect(b_right_well).set_region(".right_well")

    box_all = []
    for name, side_tool in sides.items():
        isec = b_box_fr.select_by_intersect(side_tool)
        box_all.append(isec.modify_regions("." + name))
    box_all.extend([box_fr, b_left_r, b_right_r])

    b_fractures = factory.group(*fractures_fr.get_boundary_per_region())
    b_fractures_box = b_fractures.select_by_intersect(b_box).modify_regions("{}_box")
    b_fr_left_well = b_fractures.select_by_intersect(b_left_well).modify_regions("{}_left_well")
    b_fr_right_well = b_fractures.select_by_intersect(b_right_well).modify_regions("{}_right_well")
    b_fractures = factory.group(b_fr_left_well, b_fr_right_well, b_fractures_box)
    mesh_groups = [*box_all, fractures_fr, b_fractures]



    factory.keep_only(*mesh_groups)
    factory.remove_duplicate_entities()
    factory.write_brep()

    min_el_size = well_radius / 20
    fracture_el_size = box_size / 20
    max_el_size = box_size / 10


    fractures_fr.set_mesh_step(200)
    #fracture_el_size = field.constant(100, 10000)
    #frac_el_size_only = field.restrict(fracture_el_size, fractures_fr, add_boundary=True)
    #field.set_mesh_step_field(frac_el_size_only)

    mesh = options.Mesh()
    mesh.ToleranceInitialDelaunay = 0.0001
    mesh.CharacteristicLengthFromPoints = True
    mesh.CharacteristicLengthFromCurvature = True
    mesh.CharacteristicLengthExtendFromBoundary = 1
    mesh.CharacteristicLengthMin = min_el_size
    mesh.CharacteristicLengthMax = max_el_size
    mesh.MinimumCurvePoints = 12

    factory.make_mesh(mesh_groups)
    factory.write_mesh(format=gmsh.MeshFormat.msh2)

    factory.show()



if __name__ == "__main__":
    generate_mesh()