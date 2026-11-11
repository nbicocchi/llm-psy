# Model pages are generated at build time only. No browser-side API is needed.
module LocalModelObservatory
  class ModelPages < Jekyll::Generator
    safe true
    priority :low

    def generate(site)
      profiles = site.data.fetch("model_profiles", {}).fetch("models", [])
      profiles.each do |profile|
        page = Jekyll::PageWithoutAFile.new(
          site, site.source, "models/#{profile.fetch('slug')}", "index.html"
        )
        page.data.merge!(
          "layout" => "model",
          "title" => profile.fetch("id"),
          "model" => profile
        )
        site.pages << page
      end
    end
  end
end
