# frozen_string_literal: true

# AI-dg standalone SketchUp reconstruction prototype for drawing VN-1.
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

      # Geometry Ledger values from the current geometry-first acceptance read.
      LENGTH_X_MM = 8000.0
      TOTAL_Z_MM = 1100.0
      LOWER_REGION_Z_MM = 800.0
      LOWER_BASE_Z_MM = 750.0
      TRANSITION_Z_MM = 50.0
      UPPER_GLASS_VISIBLE_Z_MM = 300.0
      TOP_RADIUS_MM = 50.0

      # CT1 local cross-section stack.
      CT1_TOTAL_Y_MM = 40.0
      CT1_LEFT_MM = 14.0
      CT1_SLOT_MM = 12.0
      CT1_RIGHT_MM = 14.0
      GLASS_THICKNESS_MM = 10.0

      # Derived review hypothesis:
      # 14 + 12 + 14 = 40, with 10 mm glass visualized centered in the 12 mm slot.
      # The centering is intentionally marked REVIEW_REQUIRED in model metadata.
      GLASS_Y_MM = CT1_LEFT_MM + ((CT1_SLOT_MM - GLASS_THICKNESS_MM) / 2.0)

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

      def add_box(parent_entities, name:, x:, y:, z:, lx:, ly:, lz:, mat:, meta:)
        group = parent_entities.add_group
        group.name = name

        pts = [
          Geom::Point3d.new(mm(x), mm(y), mm(z)),
          Geom::Point3d.new(mm(x + lx), mm(y), mm(z)),
          Geom::Point3d.new(mm(x + lx), mm(y + ly), mm(z)),
          Geom::Point3d.new(mm(x), mm(y + ly), mm(z))
        ]

        face = group.entities.add_face(pts)
        raise "Could not create face for #{name}" unless face
        face.reverse! if face.normal.z < 0
        face.pushpull(mm(lz))
        paint_all_faces(group.entities, mat) if mat
        attach_meta(group, meta)
        group
      end

      def add_wire_box(parent_entities, name:, x:, y:, z:, lx:, ly:, lz:, meta:)
        group = parent_entities.add_group
        group.name = name

        p000 = Geom::Point3d.new(mm(x), mm(y), mm(z))
        p100 = Geom::Point3d.new(mm(x + lx), mm(y), mm(z))
        p110 = Geom::Point3d.new(mm(x + lx), mm(y + ly), mm(z))
        p010 = Geom::Point3d.new(mm(x), mm(y + ly), mm(z))
        p001 = Geom::Point3d.new(mm(x), mm(y), mm(z + lz))
        p101 = Geom::Point3d.new(mm(x + lx), mm(y), mm(z + lz))
        p111 = Geom::Point3d.new(mm(x + lx), mm(y + ly), mm(z + lz))
        p011 = Geom::Point3d.new(mm(x), mm(y + ly), mm(z + lz))

        edges = [
          [p000, p100], [p100, p110], [p110, p010], [p010, p000],
          [p001, p101], [p101, p111], [p111, p011], [p011, p001],
          [p000, p001], [p100, p101], [p110, p111], [p010, p011]
        ]
        edges.each { |a, b| group.entities.add_line(a, b) }
        attach_meta(group, meta)
        group
      end

      def rounded_top_profile_points(width_mm:, y_mm:, z_bottom_mm:, z_top_mm:, radius_mm:, segments: 10)
        r = [radius_mm.to_f, (z_top_mm - z_bottom_mm).to_f / 2.0, width_mm.to_f / 2.0].min
        pts = []

        pts << Geom::Point3d.new(mm(0), mm(y_mm), mm(z_bottom_mm))
        pts << Geom::Point3d.new(mm(width_mm), mm(y_mm), mm(z_bottom_mm))
        pts << Geom::Point3d.new(mm(width_mm), mm(y_mm), mm(z_top_mm - r))

        # Top-right quarter arc: 0 -> 90 deg in X/Z plane.
        center_x_r = width_mm - r
        center_z = z_top_mm - r
        (1..segments).each do |i|
          angle = (Math::PI / 2.0) * (i.to_f / segments)
          x = center_x_r + r * Math.cos(angle)
          z = center_z + r * Math.sin(angle)
          pts << Geom::Point3d.new(mm(x), mm(y_mm), mm(z))
        end

        pts << Geom::Point3d.new(mm(r), mm(y_mm), mm(z_top_mm))

        # Top-left quarter arc: 90 -> 180 deg.
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
        group.name = 'UPPER_GLASS'

        points = rounded_top_profile_points(
          width_mm: LENGTH_X_MM,
          y_mm: GLASS_Y_MM,
          z_bottom_mm: LOWER_REGION_Z_MM,
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
          geometry_role: 'upper_glass_visible_region',
          material_role: 'GLASS + FILM_DECAL',
          status: 'DERIVED_FROM_VIEWS',
          review_required: true,
          source: SOURCE,
          notes: 'Glass 10 mm and R50 are modeled from the current read. Y position is centered inside the 12 mm CT1 slot as a review hypothesis; verify against source detail before fabrication.'
        })
        group
      end

      def validate_constants!
        raise '750 + 50 must equal lower region 800' unless (LOWER_BASE_Z_MM + TRANSITION_Z_MM - LOWER_REGION_Z_MM).abs < 0.001
        raise '800 + 300 must equal total 1100' unless (LOWER_REGION_Z_MM + UPPER_GLASS_VISIBLE_Z_MM - TOTAL_Z_MM).abs < 0.001
        raise '14 + 12 + 14 must equal CT1 total 40' unless (CT1_LEFT_MM + CT1_SLOT_MM + CT1_RIGHT_MM - CT1_TOTAL_Y_MM).abs < 0.001
        raise 'Glass must fit inside CT1 slot' unless GLASS_THICKNESS_MM <= CT1_SLOT_MM
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

        # 0..750 lower envelope. The 40 mm Y depth is a review-required local
        # hypothesis from side/detail evidence, not a fabrication claim.
        add_box(
          root.entities,
          name: 'LOWER_BODY_ENVELOPE',
          x: 0, y: 0, z: 0,
          lx: LENGTH_X_MM, ly: CT1_TOTAL_Y_MM, lz: LOWER_BASE_Z_MM,
          mat: mat_lower,
          meta: {
            item_id: 'VN-1',
            geometry_role: 'lower_body_envelope_0_750',
            material_role: 'MDF + MELAMINE REGION',
            status: 'DERIVED_FROM_VIEWS',
            review_required: true,
            source: SOURCE,
            notes: 'X/Z are constrained. Using 40 mm local depth for prototype visualization only; complete fabrication buildup remains unresolved.'
          }
        )

        # 750..800 transition: visualize the 14 / 12 / 14 CT1 cross-section.
        add_box(
          root.entities,
          name: 'TRANSITION_LEFT_LAYER',
          x: 0, y: 0, z: LOWER_BASE_Z_MM,
          lx: LENGTH_X_MM, ly: CT1_LEFT_MM, lz: TRANSITION_Z_MM,
          mat: mat_lower,
          meta: {
            item_id: 'VN-1', geometry_role: 'ct1_left_14', status: 'EXPLICIT_LOCAL_DETAIL',
            review_required: true, source: SOURCE,
            notes: 'Local CT1 layer visualized across X for prototype testing; verify whether the detail is continuous along the full length.'
          }
        )

        add_wire_box(
          root.entities,
          name: 'CT1_SEAT_ZONE_GUIDE',
          x: 0, y: CT1_LEFT_MM, z: LOWER_BASE_Z_MM,
          lx: LENGTH_X_MM, ly: CT1_SLOT_MM, lz: TRANSITION_Z_MM,
          meta: {
            item_id: 'VN-1', geometry_role: 'ct1_central_12_guide', status: 'PLACEHOLDER_GUIDE',
            review_required: true, source: SOURCE,
            notes: 'Non-fabrication guide for the 12 mm central CT1 zone. Do not count as material.'
          }
        )

        add_box(
          root.entities,
          name: 'TRANSITION_RIGHT_LAYER',
          x: 0, y: CT1_LEFT_MM + CT1_SLOT_MM, z: LOWER_BASE_Z_MM,
          lx: LENGTH_X_MM, ly: CT1_RIGHT_MM, lz: TRANSITION_Z_MM,
          mat: mat_lower,
          meta: {
            item_id: 'VN-1', geometry_role: 'ct1_right_14', status: 'EXPLICIT_LOCAL_DETAIL',
            review_required: true, source: SOURCE,
            notes: 'Local CT1 layer visualized across X for prototype testing; verify whether the detail is continuous along the full length.'
          }
        )

        add_glass(root.entities, mat_glass)

        attach_meta(root, {
          item_id: 'VN-1',
          status: 'RUBY_PROTOTYPE_PARTIAL_READY',
          component_geometry_readiness: 'PARTIAL_READY',
          project_placement_readiness: 'BLOCKED_NO_PLAN_CAD',
          project_quantity_readiness: 'BLOCKED_NO_PLAN_SCHEDULE',
          fabrication_bom_readiness: 'BLOCKED',
          source: SOURCE,
          notes: 'Local reconstruction test only. No project placement, project quantity, or fabrication BOM claim.'
        })

        model.commit_operation
        model.active_view.zoom_extents

        UI.messagebox(
          "AI-dg VN-1 prototype created.\n\n" \
          "Component geometry: PARTIAL_READY\n" \
          "Project placement: BLOCKED_NO_PLAN_CAD\n" \
          "Project quantity: BLOCKED_NO_PLAN_SCHEDULE\n" \
          "Fabrication BOM: BLOCKED\n\n" \
          "Inspect group attributes under dictionary AI_DG before accepting geometry."
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
