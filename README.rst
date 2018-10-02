kgtool: toolbox for processing knowledge graph and cnSchema



install
-------------
  pip install kgtool

additional setup
* install graphviz/dot to render schema in image
  brew install graphviz

* RDF/JSON-LD processor
  pip install rdflib-jsonld





tools
-------------

kgtool/core.py
* file utilities
* json data access
* data conversion

kgtool/stats.py
* table item statistics

kgtool cns
* cns/cns_model.py    basic cns data model, load/export jsonld
* cns/cns_convert.py  convert cns item
* cns/cns_validate.py  validate cns item
* cns/cns_graphviz.py  visualize cns schema

cns
* cns/cns_excel.py    load cnSchema schema in excel
* cns/schemaorg.py    update schemaorg
* cns/cns_schemaorg.py   convert schemaorg to loaded_schema format


cnSchema 201806
====================

### cns_top
源文件
https://docs.google.com/spreadsheets/d/1YKtEpHqa2I8LvuNAVDg3uwV6G9b4ZrNJsZdvPMS3_98/edit#gid=175537852

./genschema.sh cns_top v2.0



### cns_place
源文件
https://docs.google.com/spreadsheets/d/1aX-_QOj2GQALx-k_dJU-ak5LyvV0iIBaAg6s2N0UNmw/edit#gid=1952900205

./genschema.sh cns_place v2.0


### cns_organization
源文件
https://docs.google.com/spreadsheets/d/1qVaBhsbf0RRkrVhG0kkkn79q_fH4s4bV3oO5isGrX8o/edit#gid=659512552

./genschema.sh cns_organization v2.0


### cns_person
源文件
https://docs.google.com/spreadsheets/d/1b5DubotKUTU5tvT2pGXztwLpP63Xrc1le-VOuGKqbcw/edit

./genschema.sh cns_person v2.0




### cns_schemaorg
源文件
https://docs.google.com/spreadsheets/d/1mpiBxI5rK_qs86IpbXgN1xbhrxS_VYF0XjI_fcRpl00/edit#gid=364353024

./genschema.sh cns_schemaorg

TODO: super class/property 这一块还没有做
TODO: 形成template
TODO: 处理 domain/range


### cns_kg4ai
源文件
https://docs.google.com/spreadsheets/d/1wAM3zoyjFmo0O92-okLHLMXwKNvx_GCWV2eu_AeX3VY/edit#gid=1085464633

./genschema.sh cns_kg4ai v20180915
