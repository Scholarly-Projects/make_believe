# _plugins/trigger_tag.rb
#
# Liquid tag: {% trigger type: image id: foo action: start zoom: 12 opacity: 55 coordinates: 500,300 %}
#
# Renders a hidden span with data-* attributes read by scrollytelling-handler.js
# and intervis-handler.js.
#
# Supported parameters (all optional except type, id, action):
#   type        — trigger kind, currently always "image"
#   id          — object ID (collection item) or inter_vis layer filename stem
#   action      — "start" or "end"
#   zoom        — numeric scale factor (÷10 in JS), default blank → JS defaults to 10
#   opacity     — 0–100 integer; emitted as data-trigger-opacity for InterVis layers
#   coordinates — "x,y" in 0–1000 space for pan transform-origin

module Jekyll
  class TriggerTag < Liquid::Tag

    # Match key: value pairs, where value may be empty, a number, or a
    # comma-separated pair.  Handles trailing whitespace between pairs.
    PARAM_RE = /(\w+):\s*([^\s]*)/

    def initialize(tag_name, markup, tokens)
      super
      @params = {}
      markup.scan(PARAM_RE) do |key, value|
        @params[key.strip] = value.strip
      end
    end

    def render(context)
      type        = @params['type']        || ''
      id          = @params['id']          || ''
      action      = @params['action']      || ''
      zoom        = @params['zoom']        || ''
      opacity     = @params['opacity']     || ''
      coordinates = @params['coordinates'] || ''

      # Build data attributes selectively — omit blank values so JS
      # can distinguish "not set" from "set to empty string".
      attrs = []
      attrs << %Q(data-trigger-type="#{type}")        unless type.empty?
      attrs << %Q(data-trigger-id="#{id}")            unless id.empty?
      attrs << %Q(data-trigger-action="#{action}")    unless action.empty?
      attrs << %Q(data-trigger-zoom="#{zoom}")        unless zoom.empty?
      attrs << %Q(data-trigger-opacity="#{opacity}")  unless opacity.empty?
      attrs << %Q(data-trigger-coordinates="#{coordinates}") unless coordinates.empty?

      # Invisible block-level element; CSS and JS size/hide it appropriately
      # for each layout context (scrollytelling: 0×0; inter_vis: 80vh height).
      %Q(<span #{attrs.join(' ')}></span>)
    end
  end
end

Liquid::Template.register_tag('trigger', Jekyll::TriggerTag)