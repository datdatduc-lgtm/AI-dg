# frozen_string_literal: true

# AI-DG MCP-SU toolbar. It owns exactly one toolbar and one command; it never
# resets, enumerates, moves, or changes any toolbar belonging to another plugin.

module AI_DG
  module Bridge
    require_relative 'control_center'

    TOOLBAR_NAME = 'AI-DG MCP-SU Control Center' unless const_defined?(:TOOLBAR_NAME, false)
    TOOLBAR_COMMAND_NAME = 'AI-DG Control Center' unless const_defined?(:TOOLBAR_COMMAND_NAME, false)

    class << self
      def ensure_toolbar
        return @toolbar if @toolbar

        icon_path = File.join(__dir__, 'icons', 'ai_dg_mcp.svg')
        raise LoadError, "Missing AI-DG toolbar icon: #{icon_path}" unless File.file?(icon_path)

        @command = UI::Command.new(TOOLBAR_COMMAND_NAME) { ControlCenter.open }
        @command.small_icon = icon_path
        @command.large_icon = icon_path
        @command.tooltip = TOOLBAR_NAME
        @command.status_bar_text = 'Mở AI-DG MCP-SU Control Center'
        @command.menu_text = TOOLBAR_COMMAND_NAME
        @command.set_validation_proc { runtime_active? ? MF_ENABLED : MF_GRAYED }

        @toolbar = UI::Toolbar.new(TOOLBAR_NAME)
        @toolbar.add_item(@command)
        @toolbar.show
        log("toolbar_created name=#{TOOLBAR_NAME.inspect} icon=#{icon_path.inspect}")
        @toolbar
      rescue StandardError => e
        log_exception('toolbar', e) if respond_to?(:log_exception, true)
        @toolbar = nil
        @command = nil
        nil
      end

      def toolbar_info
        return { status: 'not_created', name: TOOLBAR_NAME } unless @toolbar

        {
          status: 'created',
          name: TOOLBAR_NAME,
          visible: @toolbar.visible?,
          item_count: @toolbar.length,
          command: @command.menu_text,
          small_icon: @command.small_icon,
          large_icon: @command.large_icon
        }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}" }
      end

      private
    end
  end
end
