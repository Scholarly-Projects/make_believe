# _plugins/trigger_tag.rb
#
# Usage:
#   {% trigger type: image id: foo action: start opacity: 90 coordinates: 600,500 description: "Caption text" %}
#   {% trigger type: image id: foo action: end %}
#   {% trigger type: image id: all action: end %}
#
# Rules:
#   - Omit any field you don't need. zoom: omitted = default 10 (1x scale).
#   - description: requires a quoted string: description: "text here"
#   - coordinates: takes unquoted x,y values: coordinates: 600,500
#   - Multiple ids: id: foo, bar  (comma-separated, no quotes needed)
#
# IMPORTANT: After editing this file, you MUST fully stop and restart
# `bundle exec jekyll serve`. The --watch flag does NOT reload plugins.

module Jekyll
  class TriggerTag < Liquid::Tag

    KNOWN_KEYS = %w[type id action opacity zoom coordinates description].freeze

    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(context)
      attrs = parse_attrs(@markup)

      type        = attrs.fetch('type',        '').strip
      id_val      = attrs.fetch('id',          '').strip
      action      = attrs.fetch('action',      'start').strip
      opacity     = attrs.fetch('opacity',     '').strip
      zoom        = attrs.fetch('zoom',        '').strip
      coordinates = attrs.fetch('coordinates', '').strip
      description = attrs.fetch('description', '').strip

      html  = '<span '
      html += %(data-trigger-type="#{type}" )               unless type.empty?
      html += %(data-trigger-id="#{id_val}" )               unless id_val.empty?
      html += %(data-trigger-action="#{action}" )
      html += %(data-trigger-opacity="#{opacity}" )         unless opacity.empty?
      html += %(data-trigger-zoom="#{zoom}" )               unless zoom.empty?
      html += %(data-trigger-coordinates="#{coordinates}" ) unless coordinates.empty?
      html += %(data-trigger-description="#{html_escape(description)}" ) unless description.empty?
      html += '></span>'
      html
    end

    private

    def html_escape(str)
      str.to_s
         .gsub('&', '&amp;')
         .gsub('"', '&quot;')
         .gsub("'", '&#39;')
         .gsub('<', '&lt;')
         .gsub('>', '&gt;')
    end

    # Position-based tokenizer.
    #
    # Finds every known KEY: occurrence in the markup string and records its
    # byte position. Each key's value is then the raw text between that key's
    # value-start and the next key's match-start.
    #
    # This correctly handles:
    #   - Adjacent empty fields: "zoom: coordinates: 175,720"
    #     zoom  → "" (val_begin == next match_begin, length 0)
    #     coordinates → "175,720"
    #   - Quoted strings: description: "text with spaces, and commas"
    #   - Omitted fields: if zoom: never appears, attrs['zoom'] is absent.
    #
    # Uses String#match(pattern, offset) rather than scan+Regexp.last_match
    # to avoid any Regexp.last_match thread-safety or block-scope issues.
    def parse_attrs(markup)
      attrs   = {}
      key_alt = KNOWN_KEYS.map { |k| Regexp.escape(k) }.join('|')
      pattern = /\b(#{key_alt}):\s*/

      # Collect [key, match_begin, val_begin] for every known-key occurrence
      positions = []
      offset = 0
      loop do
        m = markup.match(pattern, offset)
        break unless m
        positions << [m[1], m.begin(0), m.end(0)]
        offset = m.end(0)
      end

      # Extract value for each key
      positions.each_with_index do |(key, _match_begin, val_begin), i|
        # Value ends where the NEXT key's token starts (not where its value starts)
        val_end = i + 1 < positions.size ? positions[i + 1][1] : markup.length
        raw     = markup[val_begin, val_end - val_begin].to_s.strip

        # Strip surrounding double or single quotes from string literals
        if raw.length >= 2 &&
           ((raw.start_with?('"') && raw.end_with?('"')) ||
            (raw.start_with?("'") && raw.end_with?("'")))
          raw = raw[1..-2]
        end

        attrs[key] = raw
      end

      attrs
    end
  end
end

Liquid::Template.register_tag('trigger', Jekyll::TriggerTag)