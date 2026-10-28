// Dimensions in millimetres
length = 100;
width = 80;
height = 27;
wall = 3;
base = 2;
corner_radius = 5;
hole_diameter = 6;
hole_inset = 10;

slot_length = 12;
slot_height = 6;
slot_bottom_above_floor = 8;

lid_thickness = 2;
lip_thickness = 1;
lip_depth = 3;
lip_clearance = 0.25; // per side
part_gap = 10;

$fn = 48;

module rounded_block(l, w, h, r) {
    hull() {
        for (x = [r, l-r])
            for (y = [r, w-r])
                translate([x, y, 0])
                    cylinder(h = h, r = r);
    }
}

module box() {
    difference() {
        rounded_block(length, width, height, corner_radius);

        // Interior follows the outside corners for uniform walls.
        translate([wall, wall, base])
            rounded_block(length - 2*wall, width - 2*wall,
                          height - base + 1, corner_radius - wall);

        for (x = [hole_inset, length - hole_inset])
            for (y = [hole_inset, width - hole_inset])
                translate([x, y, -1])
                    cylinder(h = base + 2, d = hole_diameter);

        // Horizontal capsule slot through the long wall at y = 0.
        hull() {
            for (x = [length/2 - (slot_length - slot_height)/2,
                      length/2 + (slot_length - slot_height)/2])
                translate([x, wall + 1,
                           base + slot_bottom_above_floor + slot_height/2])
                    rotate([90, 0, 0])
                        cylinder(h = wall + 2, d = slot_height);
        }
    }
}

module lid() {
    lip_offset = wall + lip_clearance;
    lip_length = length - 2*lip_offset;
    lip_width = width - 2*lip_offset;
    lip_radius = corner_radius - lip_offset;

    rounded_block(length, width, lid_thickness, corner_radius);

    // Lip faces upward for printing; flip the lid to fit it on the box.
    translate([lip_offset, lip_offset, lid_thickness])
        difference() {
            rounded_block(lip_length, lip_width, lip_depth, lip_radius);
            translate([lip_thickness, lip_thickness, -1])
                rounded_block(lip_length - 2*lip_thickness,
                              lip_width - 2*lip_thickness,
                              lip_depth + 2, lip_radius - lip_thickness);
        }
}

box();
translate([length + part_gap, 0, 0]) lid();