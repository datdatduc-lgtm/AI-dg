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
  end
end
