module Jekyll
  class TriggerTag < Liquid::Tag
    def initialize(tag_name, text, tokens)
      super
      @params = {}
      
      # Parse the parameters
      text.scan(/(\w+):\s*([^\s]+)/) do |name, value|
        @params[name.strip] = value.strip
      end
    end

    def render(context)
      # Build the HTML div with the parameters
      html = "<div data-trigger-type=\"#{@params['type']}\" "
      html += "data-trigger-id=\"#{@params['id']}\" "
      html += "data-trigger-action=\"#{@params['action']}\" "
      
      if @params['zoom']
        html += "data-trigger-zoom=\"#{@params['zoom']}\" "
      end
      
      if @params['coordinates']
        html += "data-trigger-coordinates=\"#{@params['coordinates']}\" "
      end
      
      if @params['text']
        # Escape the text to prevent HTML injection
        escaped_text = @params['text'].gsub('"', '&quot;')
        html += "data-trigger-text=\"#{escaped_text}\" "
      end
      
      html += "style=\"height: 2px; background: transparent; margin: 1rem 0;\"></div>"
      
      html
    end
  end
end

Liquid::Template.register_tag('trigger', Jekyll::TriggerTag)