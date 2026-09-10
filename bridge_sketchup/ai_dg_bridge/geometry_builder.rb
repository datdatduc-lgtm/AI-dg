# frozen_string_literal: true
# AI-DG Parametric Geometry Helper Library for SketchUp

module AI_DG
  module Geometry
    extend self

    DICT_NAME = 'AI_DG'

    def mm(val)
      val.to_f.mm
    end

    def attach_meta(entity, data = {})
      data.each do |key, val|
        entity.set_attribute(DICT_NAME, key.to_s, val)
      end
    end

    def get_or_create_material(model, name, rgb = [200, 200, 200], alpha = 1.0)
      mat = model.materials[name] || model.materials.add(name)
      mat.color = Sketchup::Color.new(*rgb)
      mat.alpha = alpha
      mat
    end

    def paint_entity(entity, mat)
      if entity.is_a?(Sketchup::Face)
        entity.material = mat
        entity.back_material = mat
      elsif entity.respond_to?(:entities)
        entity.entities.grep(Sketchup::Face).each do |face|
          face.material = mat
          face.back_material = mat
        end
      end
    end

    # Tạo một khối hộp Rectangular Box tại tọa độ gốc (origin_x, origin_y, origin_z)
    def create_box(parent_entities, width_x, depth_y, height_z, origin = [0, 0, 0], mat = nil, meta = {})
      group = parent_entities.add_group
      ox, oy, oz = origin

      pts = [
        [mm(ox), mm(oy), mm(oz)],
        [mm(ox + width_x), mm(oy), mm(oz)],
        [mm(ox + width_x), mm(oy + depth_y), mm(oz)],
        [mm(ox), mm(oy + depth_y), mm(oz)]
      ]

      face = group.entities.add_face(pts)
      raise ArgumentError, 'BOX_FACE_CREATION_FAILED' unless face
      face.reverse! if face.normal.z < 0
      face.pushpull(mm(height_z))

      paint_entity(group, mat) if mat
      attach_meta(group, meta) unless meta.empty?

      group
    end

    # Tạo panel soi rãnh hoặc rãnh kính (slotted panel)
    def create_slotted_panel(parent_entities, length_x, depth_y, lower_z, slot_width_y, slot_depth_z, mat = nil, meta = {})
      group = parent_entities.add_group
      side_y = (depth_y - slot_width_y) / 2.0

      # Profile chữ U ngược hoặc mặt cắt Y/Z
      # Điểm mặt cắt tại X=0
      pts = [
        [0, 0, 0],
        [0, mm(depth_y), 0],
        [0, mm(depth_y), mm(lower_z)],
        [0, mm(depth_y - side_y), mm(lower_z)],
        [0, mm(depth_y - side_y), mm(lower_z - slot_depth_z)],
        [0, mm(side_y), mm(lower_z - slot_depth_z)],
        [0, mm(side_y), mm(lower_z)],
        [0, 0, mm(lower_z)]
      ]

      face = group.entities.add_face(pts)
      face.pushpull(-mm(length_x))

      paint_entity(group, mat) if mat
      attach_meta(group, meta) unless meta.empty?

      group
    end

    # Extrude an arbitrary closed Y/Z section along X.  This is the primitive
    # used by reconstruction V3: section evidence remains section geometry and
    # is not flattened into a stack of rectangular boxes.
    def create_profile_extrusion(parent_entities, length_x, profile_yz, mat = nil, meta = {})
      raise ArgumentError, 'PROFILE_LENGTH_INVALID' unless length_x.to_f.positive?
      raise ArgumentError, 'PROFILE_POINTS_INVALID' unless profile_yz.is_a?(Array) && profile_yz.length >= 3

      group = parent_entities.add_group
      points = profile_yz.map do |pair|
        raise ArgumentError, 'PROFILE_POINT_INVALID' unless pair.is_a?(Array) && pair.length == 2

        [0, mm(Float(pair[0])), mm(Float(pair[1]))]
      end
      face = group.entities.add_face(points)
      raise ArgumentError, 'PROFILE_FACE_CREATION_FAILED' unless face && face.valid?

      face.pushpull(mm(length_x))
      measured = group.bounds.width.to_mm
      if (measured - length_x.to_f).abs > 0.1
        # Face winding controls extrusion direction, not its required length.
        raise RuntimeError, 'PROFILE_EXTRUSION_VERIFY_FAILED'
      end
      paint_entity(group, mat) if mat
      attach_meta(group, meta) unless meta.empty?
      group
    end

    # Build an X/Z panel outline with rounded top corners and extrude it along
    # Y. Arc points remain measurable by native view-back.
    def create_rounded_top_panel(parent_entities, width_x, depth_y, height_z, origin, radius, mat = nil, meta = {})
      width_x = Float(width_x)
      depth_y = Float(depth_y)
      height_z = Float(height_z)
      radius = Float(radius)
      raise ArgumentError, 'ROUNDED_PANEL_DIMENSIONS_INVALID' unless [width_x, depth_y, height_z, radius].all?(&:positive?)
      raise ArgumentError, 'ROUNDED_PANEL_RADIUS_INVALID' unless radius * 2 < width_x && radius < height_z

      group = parent_entities.add_group
      points_xz = [[0.0, 0.0], [width_x, 0.0], [width_x, height_z - radius]]
      segments = 8
      (1..segments).each do |index|
        angle = index * Math::PI / (2.0 * segments)
        points_xz << [width_x - radius + radius * Math.cos(angle), height_z - radius + radius * Math.sin(angle)]
      end
      points_xz << [radius, height_z]
      (1..segments).each do |index|
        angle = Math::PI / 2.0 + index * Math::PI / (2.0 * segments)
        points_xz << [radius + radius * Math.cos(angle), height_z - radius + radius * Math.sin(angle)]
      end
      face = group.entities.add_face(points_xz.map { |x, z| [mm(x), 0, mm(z)] })
      raise ArgumentError, 'ROUNDED_PANEL_FACE_CREATION_FAILED' unless face && face.valid?
      face.pushpull(mm(depth_y))
      bounds = group.bounds
      target = origin.map { |value| mm(Float(value)) }
      shift = Geom::Vector3d.new(target[0] - bounds.min.x, target[1] - bounds.min.y, target[2] - bounds.min.z)
      group.transform!(Geom::Transformation.translation(shift))
      paint_entity(group, mat) if mat
      attach_meta(group, meta) unless meta.empty?
      group
    end
  end
end
