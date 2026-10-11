---
type: owl:DatatypeProperty
label: method
comment: "The step-by-step instructions for preparing a recipe, as Markdown."
domain: [ "[[Recipe]]" ]
range:  [ xsd:string ]
tags: [ owl-property, Culinary ]
---
# method
A datatype property whose values are usually too long and too structured for a YAML scalar. Instance notes hold it as a **section reference** (SPEC §4.4.2): the frontmatter says `method: "[[#Method]]"`, the steps are written as ordinary Markdown under a `## Method` heading in the body, and the exported literal is that section's content.
