module LocalModelObservatory
  class StimulusPages < Jekyll::Generator
    safe true
    priority :low

    def generate(site)
      site.data.fetch("stimuli", {}).fetch("stimuli", []).each do |stimulus|
        page = Jekyll::PageWithoutAFile.new(
          site, site.source, "stimuli/#{stimulus.fetch('slug')}", "index.html"
        )
        page.data.merge!("layout" => "stimulus", "title" => stimulus.fetch("title"), "stimulus" => stimulus)
        site.pages << page
      end
    end
  end
end
