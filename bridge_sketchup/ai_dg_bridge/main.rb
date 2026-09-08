# frozen_string_literal: true

# Canonical source entrypoint for manual installs.
#
# The production implementation lives in main_safe.rb so the staged runtime
# and the repository entrypoint cannot silently diverge. deploy_bridge.ps1
# still stages main_safe.rb directly as the installed main.rb to keep the
# deployed source hash explicit.
require_relative 'main_safe'
