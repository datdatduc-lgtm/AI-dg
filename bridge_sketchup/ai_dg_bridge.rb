# frozen_string_literal: true
# AI-DG SketchUp Extension Loader
require 'sketchup.rb'
require 'extensions.rb'

module AI_DG
  module Bridge
    unless file_loaded?(__FILE__)
      main_file = File.join(File.dirname(__FILE__), 'ai_dg_bridge', 'main.rb')
      EXTENSION = SketchupExtension.new('AI-DG MCP Bridge', main_file) unless const_defined?(:EXTENSION, false)
      EXTENSION.description = 'Cầu nối MCP headless tới SketchUp Ruby API chính thức. Không toolbar, không HtmlDialog, không AI runtime nhúng.'
      EXTENSION.version     = '1.1.0'
      EXTENSION.creator     = 'AI-DG Team'

      # The extension loader is intentionally the only startup entry point.
      # The deployed main.rb schedules its runtime after SketchUp is idle.
      Sketchup.register_extension(EXTENSION, true)

      file_loaded(__FILE__)
    end
  end
end
