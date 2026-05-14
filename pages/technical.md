---
title: Technical Notes
layout: about
permalink: /technical.html
credits: false
hide-default-footer: true
---
<style>
  #about-contents-wrapper p {
    font-size: clamp(0.92rem, 1.15vw, 1.05rem);
    line-height: 2;
    color: rgba(17, 17, 17, 0.65);
    margin: 0;
    text-indent: 2em;
    text-align: left;
  }
  #about-contents-wrapper ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  #about-contents-wrapper ul li {
    font-size: clamp(0.92rem, 1.15vw, 1.05rem);
    line-height: 2;
    color: rgba(17, 17, 17, 0.65);
    padding-left: 2em;
    text-indent: -2em;
  }
  #about-contents-wrapper ul li::before {
    content: "–\00a0";
    color: rgba(17, 17, 17, 0.65);
  }
</style>

## Technical Notes

<br>

[Vis-arly](https://github.com/Scholarly-Projects/vis-arly) is a static web essay template currently in active development, designed to support visually-driven scholarly publications in the humanities. The template is an iteration of [CB-Essay](https://collectionbuilder.github.io/cb-essay/) developed by Devin Becker, one of the many versions of [CollectionBuilder](https://collectionbuilder.github.io/) created by the [Center for Digital Inquiry and Learning (CDIL)](https://cdil.lib.uidaho.edu/) at University of Idaho’s library.

The project was initially developed to host the author’s Master’s thesis, which examines the history of Dutch financial monopoly in Spokane, Washington and the city’s expressions of exclusionary and aspirational iconography through pageantry, commercial iconography and architecture. To support this visual resource-oriented study that closely analyzes archival images, I wanted to develop a digital framework that allowed the reader to engage seamlessly with the text, features and citations, while still meeting the academic rigour of a traditional thesis.

Vis-arly follows CollectionBuilder's static hosting approach, generating a lightweight reading interface from CSV-driven metadata, Javascript handling and Markdown-formatted essay content. The template emphasizes a minimal, horizontally oriented design in which essay images and text citations remain “sticky” as readers scroll vertically through the text. This creates the sense that nothing is hidden beneath the interface while presenting only the most relevant supporting material at any given moment.

The scrollytelling-handler Javascript allows authors to place their images and citations strategically in their markdown files, which are triggered as the reader scrolls through the text. Additionally, the liquid commands which trigger images to start and stop within a passage allow the author to set XY coordinates and zoom levels, which adds a dynamic but completely programmatic control over the reading experience. 

The interface is designed to present readers with only the most relevant reference material. Citations appear to the right of the passages they reference as the reader scrolls, while image citations appear beneath figures based on how the author arranges them within each chapter’s markdown files. This information is generated from CSV files that automatically create scholarly formatted bibliography and image credit pages, allowing updates to a single file to propagate throughout the site. Additionally, if citations need to be added or removed during the editing process, a simple Python script is included to seamlessly update citation numbering across all chapters.

An interstitial visualization function expands on the scrollytelling handler concept by allowing authors to place data visualizations between chapters that progress as the reader scrolls. This approach provides additional context without redirecting readers to another section of the site. These “inter-vis” elements automatically adjust to reader display preferences, and a shared alt-text field for each visualization layer offers a creative solution to many of the accessibility challenges associated with data visualizations.

Additional features were developed to reduce friction in the reading experience and foreground the archival material. An “infinite scroll” function allows readers to move seamlessly between essay chapters without navigating drop-down menus. Scroll state preservation ensures that readers who follow a citation or image link out to a collection item are returned to their exact position in the text on return. The site also supports light and dark mode, full mobile adaptability, and a dual keyboard navigation track that allows readers to cycle between site-level pages or drop to item-level pages independently.

Together, these features position Vis-arly as a reusable and adaptable framework for scholars working at the intersection of archival research, digital publication, and public-facing scholarship.