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
<p>To support the visual resource-oriented nature of this project, I wanted to develop a digital exhibit template that would allow readers the ability to allow these images to be in dialogue with the research to underpin the historical argument of the thesis. The resulting essay template, named <a href="https://github.com/Scholarly-Projects/textemporal">Textemporal</a>, is an iteration of my colleague Devin Becker's <a href="https://collectionbuilder.github.io/cb-essay/">CB Essay</a> and follows CollectionBuilder's static web hosting approach. The template was specifically designed to support scholarly, proving the reader with just enough information to help them move through the research material while keeping the reading interface minimal and lightweight.</p>

### Template Features

<ul>
  <li>Reading interface is designed to set off a series of citation and image triggers, which are set off as the reader progresses through the text.</li>
  <li>"Sticky" media configuration where images remain static as the text scrolls through vertically, intended for a more concentrated, unified reading experience.</li>
  <li>Sidebar which generates a text citation following the reader's progress through the material, providing only the most relevant information without cluttering the interface.</li>
  <li>Programmatic manipulation of how images display, where the author of the template can enter zoom and coordinate data in the _essay markdown templates to control how readers view the media as they scroll through the text.</li>
  <li>Citations and images are informed by CSV data, allowing for automatic generation and editing of Image Credit and Bibliography pages.</li>
  <li>"Infinite Scroll" function, which allows readers to seamlessly scroll from one chapter to another in the _essay section of the site, so they can remain focused on the text, rather than hunting in menu drop downs to progress. Images and citations are triggered identically moving both forward and backwards in the text like an audio recording, which is where the temporal in the <code>Textemporal</code> comes from.</li>
  <li>Scroll state preservation, to ensure that the reader is returned where they left in the chapter, if they engage with the associated item level images or text citations.</li>
  <li>Chapters seamlessly transition between left, right and center orientation, initiated by a customizable chapter transition icon. Any seams in the layout are masked by scrolling progress based fades.</li>
  <li>Light / Dark mode toggle.</li>
  <li>Mobile configuration, which displays images and their associated citations in full.</li>
  <li>Minimal, horizontally-oriented site design.</li>
  <li>Dual navigation tracks: readers can quickly use arrow keys to cycle through site level pages (home, browse, map, etc.), or drop down to the item level pages to cycle through that material.</li>
  <li>Retains CollectionBuilder's database-oriented approach allowing readers to dive deeper into the media that compliments the essay material and make further research connections by visualizing those items chronologically, geographically or thematically.</li>
</ul>