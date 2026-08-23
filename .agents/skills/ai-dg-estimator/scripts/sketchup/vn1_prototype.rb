# frozen_string_literal: true

# AI-dg standalone SketchUp reconstruction prototype for drawing VN-1.
#
# Geometry correction learned from projection-back testing:
# - the section chain 750 + 50 refines the 800 mm lower region;
# - the 50 mm zone is an EMBED/SLOT depth for the glass, not a visible
#   horizontal transition band in the front elevation;
# - the lower body therefore keeps a continuous 800 mm front silhouette;
# - the glass extends 50 mm down into the 12 mm central slot and 300 mm above
#   the lower body, for a total glass height of 350 mm.
#
# Purpose:
# - test Geometry Ledger -> SketchUp geometry before building a plugin;
# - preserve explicit/derived/review metadata in AttributeDictionary;
# - create a LOCAL component at origin only;
# - do NOT claim project placement, project quantity, or fabrication BOM.
#
# Usage in SketchUp Ruby Console:
#   load 'C:/path/to/vn1_prototype.rb'
#
# The script replaces only a previous top-level group named AI-DG_TEST_VN-1.

require 'sketchup.rb'

module AI_DG
  module Prototype
    module VN1
      extend self

      DICT = 'AI_DG'
      ROOT_NAME = 'AI-DG_TEST_VN-1'
      SOURCE = 'CHI TIET VACH NGAN VN-1.pdf | page 1'

      # Main X/Z geometry from linked views.
      LENGTH_X_MM = 8000.0
      TOTAL_Z_MM = 1100.0
      LOWER_REGION_Z_MM = 800.0
      SLOT_BOTTOM_Z_MM = 750.0
      SLOT_DEPTH_Z_MM = 50.0
      GLASS_EXPOSED_Z_MM = 300.0
      GLASS_TOTAL_Z_MM = SLOT_DEPTH_Z_MM + GLASS_EXPOSED_Z_MM
      TOP_RADIUS_MM = 50.0

      # CT1 local Y cross-section.
      CT1_TOTAL_Y_MM = 40.0
      CT1_LEFT_MM = 14.0
      CT1_SLOT_MM = 12.0
      CT1_RIGHT_MM = 14.0
      GLASS_THICKNESS_MM = 10.0

      # 14 + 12 + 14 is symmetric. The drawing also shows a 10 mm glass in
      # the central slot with silicone. Centering the 10 mm glass leaves a
      # 1 mm review gap on each side inside the 12 mm slot.
      SLOT_SIDE_CLEARANCE_MM = (CT1_SLOT_MM - GLASS_THICKNESS_MM) / 2.0
      GLASS_Y_MM = CT1_LEFT_MM + SLOT_SIDE_CLEARANCE_MM

      def mm(value)
        value.to_f.mm
      end

      def attach_meta(entity, data)
        data.each { |key, value| entity.set_attribute(DICT, key.to_s, value) }
      end

      def material(model, name, rgb, alpha = 1.0)
        mat = model.materials[name] || model.materials.add(name)
        mat.color = Sketchup::Color.new(*rgb)
        mat.alpha = alpha
        mat
      end

      def paint_all_faces(entities, mat)
        entities.grep(Sketchup::Face).each do |face|
          face.material = mat
          face.back_material = mat
        end
      end

      # Create the lower body as ONE continuous extrusion with a 12 mm wide,
      # 50 mm deep top slot. This avoids the false horizontal seam at Z=750
      # that appeared when 750 and 50 were modeled as separate visible bands.
      #
      # Cross-section in the Y/Z plane at X=0:
      #
      #   Y=0          14      12       14          Y=40
      #    |-----------|<--- SLOT --->|-------------|
      #    |           |              |             |  Z=800
      #    |           |              |             |
      #    |           +--------------+             |  Z=750
      #    |                                        |
      #    |                                        |
      #    +----------------------------------------+  Z=0
      #
      def add_lower_body_with_slot(parent_entities, mat)
        group = parent_entities.add_group
        group.name = 'LOWER_BODY_WITH_GLASS_SLOT'

        y0 = 0.0
        y1 = CT1_LEFT_MM
        y2 = CT1_LEFT_MM + CT1_SLOT_MM
        y3 = CT1_TOTAL_Y_MM
        z0 = 0.0
        z_slot = SLOT_BOTTOM_Z_MM
        z_top = LOWER_REGION_Z_MM

        # Counter-clockwise profile in Y/Z so the normal points +X.
        points = [
          Geom::Point3d.new(mm(0), mm(y0), mm(z0)),
          Geom::Point3d.new(mm(0), mm(y3), mm(z0)),
          Geom::Point3d.new(mm(0), mm(y3), mm(z_top)),
          Geom::Point3d.new(mm(0), mm(y2), mm(z_top)),
          Geom::Point3d.new(mm(0), mm(y2), mm(z_slot)),
          Geom::Point3d.new(mm(0), mm(y1), mm(z_slot)),
          Geom::Point3d.new(mm(0), mm(y1), mm(z_top)),
          Geom::Point3d.new(mm(0), mm(y0), mm(z_top))
        ]

        face = group.entities.add_face(points)
        raise 'Could not create VN-1 lower-body slotted profile' unless face
        face.reverse! if face.normal.x < 0
        face.pushpull(mm(LENGTH_X_MM))
        paint_all_faces(group.entities, mat)

        attach_meta(group, {
          item_id: 'VN-1',
          geometry_role: 'lower_body_continuous_800_with_central_slot_12x50',
          material_role: 'MDF + MELAMINE REGION',
          status: 'DERIVED_FROM_VIEWS',
          review_required: true,
          source: SOURCE,
          lower_visible_height_mm: LOWER_REGION_Z_MM,
          slot_width_mm: CT1_SLOT_MM,
          slot_depth_mm: SLOT_DEPTH_Z_MM,
          ct1_stack_mm: '14 + 12 + 14 = 40',
          notes: 'The 50 mm section refinement is modeled as a hidden top slot/embed depth, not a visible front-elevation band. Full fabrication buildup remains review-required.'
        })

        group
      end

      def rounded_top_profile_points(width_mm:, y_mm:, z_bottom_mm:, z_top_mm:, radius_mm:, segments: 12)
        r = [radius_mm.to_f, (z_top_mm - z_bottom_mm).to_f / 2.0, width_mm.to_f / 2.0].min
        pts = []

        pts << Geom::Point3d.new(mm(0), mm(y_mm), mm(z_bottom_mm))
        pts << Geom::Point3d.new(mm(width_mm), mm(y_mm), mm(z_bottom_mm))
        pts << Geom::Point3d.new(mm(width_mm), mm(y_mm), mm(z_top_mm - r))

        # Top-right quarter arc.
        center_x_r = width_mm - r
        center_z = z_top_mm - r
        (1..segments).each do |i|
          angle = (Math::PI / 2.0) * (i.to_f / segments)
          x = center_x_r + r * Math.cos(angle)
          z = center_z + r * Math.sin(angle)
          pts << Geom::Point3d.new(mm(x), mm(y_mm), mm(z))
        end

        pts << Geom::Point3d.new(mm(r), mm(y_mm), mm(z_top_mm))

        # Top-left quarter arc.
        center_x_l = r
        (1..segments).each do |i|
          angle = (Math::PI / 2.0) + (Math::PI / 2.0) * (i.to_f / segments)
          x = center_x_l + r * Math.cos(angle)
          z = center_z + r * Math.sin(angle)
          pts << Geom::Point3d.new(mm(x), mm(y_mm), mm(z))
        end

        pts
      end

      def add_glass(parent_entities, mat)
        group = parent_entities.add_group
        group.name = 'GLASS_10MM_EMBED_50_EXPOSED_300'

        # Glass begins at Z=750, passes through the hidden 50 mm slot, and is
        # visible above the body from Z=800..1100 (300 mm exposed).
        points = rounded_top_profile_points(
          width_mm: LENGTH_X_MM,
          y_mm: GLASS_Y_MM,
          z_bottom_mm: SLOT_BOTTOM_Z_MM,
          z_top_mm: TOTAL_Z_MM,
          radius_mm: TOP_RADIUS_MM
        )

        face = group.entities.add_face(points)
        raise 'Could not create VN-1 glass profile' unless face
        face.reverse! if face.normal.y < 0
        face.pushpull(mm(GLASS_THICKNESS_MM))
        paint_all_faces(group.entities, mat)

        attach_meta(group, {
          item_id: 'VN-1',
          geometry_role: 'glass_total_350_embedded_50_exposed_300',
          material_role: 'GLASS + FILM_DECAL',
          status: 'DERIVED_FROM_VIEWS',
          review_required: true,
          source: SOURCE,
          glass_thickness_mm: GLASS_THICKNESS_MM,
          glass_total_height_mm: GLASS_TOTAL_Z_MM,
          glass_embedded_height_mm: SLOT_DEPTH_Z_MM,
          glass_exposed_height_mm: GLASS_EXPOSED_Z_MM,
          slot_side_clearance_each_mm: SLOT_SIDE_CLEARANCE_MM,
          notes: 'Glass is centered in the 12 mm CT1 slot: 10 mm glass + 1 mm review clearance each side. Silicone is indicated by the detail; exact bead geometry is not fabricated by this prototype.'
        })

        group
      end

      def validate_constants!
        raise '750 + 50 must equal lower visible region 800' unless (SLOT_BOTTOM_Z_MM + SLOT_DEPTH_Z_MM - LOWER_REGION_Z_MM).abs < 0.001
        raise '800 + 300 must equal total 1100' unless (LOWER_REGION_Z_MM + GLASS_EXPOSED_Z_MM - TOTAL_Z_MM).abs < 0.001
        raise '14 + 12 + 14 must equal CT1 total 40' unless (CT1_LEFT_MM + CT1_SLOT_MM + CT1_RIGHT_MM - CT1_TOTAL_Y_MM).abs < 0.001
        raise 'Glass must fit inside CT1 slot' unless GLASS_THICKNESS_MM <= CT1_SLOT_MM
        raise 'Glass total height must equal embed + exposed' unless (GLASS_TOTAL_Z_MM - SLOT_DEPTH_Z_MM - GLASS_EXPOSED_Z_MM).abs < 0.001
      end

      def erase_previous!(model)
        old = model.entities.grep(Sketchup::Group).find { |g| g.valid? && g.name == ROOT_NAME }
        old.erase! if old && old.valid?
      end

      def run
        validate_constants!

        model = Sketchup.active_model
        model.start_operation('AI-dg VN-1 Ruby Prototype', true)

        erase_previous!(model)
        root = model.entities.add_group
        root.name = ROOT_NAME

        mat_lower = material(model, 'AI_DG_MDF_MELAMINE_REVIEW', [190, 190, 190], 1.0)
        mat_glass = material(model, 'AI_DG_GLASS_DECAL_REVIEW', [90, 170, 155], 0.45)

        add_lower_body_with_slot(root.entities, mat_lower)
        add_glass(root.entities, mat_glass)

        attach_meta(root, {
          item_id: 'VN-1',
          status: 'RUBY_PROTOTYPE_PARTIAL_READY_V2',
          component_geometry_readiness: 'PARTIAL_READY',
          project_placement_readiness: 'BLOCKED_NO_PLAN_CAD',
          project_quantity_readiness: 'BLOCKED_NO_PLAN_SCHEDULE',
          fabrication_bom_readiness: 'BLOCKED',
          projection_back_front: 'EXPECTED_PASS_NO_Z750_VISIBLE_SEAM',
          projection_back_side_detail: 'RETEST_REQUIRED',
          source: SOURCE,
          notes: 'V2 corrects the 50 mm refinement from a visible transition band to an embedded glass-slot depth. Local reconstruction test only.'
        })

        model.commit_operation
        model.active_view.zoom_extents

        UI.messagebox(
          "AI-dg VN-1 prototype V2 created.\n\n" \
          "Corrected:\n" \
          "- no visible Z=750 transition seam in front\n" \
          "- 12 mm slot is 50 mm deep\n" \
          "- 10 mm glass embeds 50 mm and exposes 300 mm\n\n" \
          "Please retest front, side and CT1 views."
        )

        root
      rescue StandardError => e
        model.abort_operation if model
        puts "AI-dg VN-1 prototype ERROR: #{e.class}: #{e.message}"
        puts e.backtrace.join("\n")
        raise
      end
    end
  end
end

AI_DG::Prototype::VN1.run
