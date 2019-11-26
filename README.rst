kgtool: toolbox for processing knowledge graph and cnSchema



install
-------------
  pip install kgtool

additional setup
* install graphviz/dot to render schema in image
  brew install graphviz

* RDF/JSON-LD processor
  pip install rdflib-jsonld


setup
-------------
python3 -m venv ~/envs/cns-env
source ~/envs/cns-env/bin/activate



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

### cns_meta
源文件
https://docs.google.com/spreadsheets/d/1PYGYZtQLaLa2Oo3HLaL33VyL9VkUJUruYJr6nKQH6EY/edit

./genschema.sh cns_meta v2.1 schema

### cns_top
源文件
https://docs.google.com/spreadsheets/d/1YKtEpHqa2I8LvuNAVDg3uwV6G9b4ZrNJsZdvPMS3_98/edit

./genschema.sh cns_top v2.3 schema

### cns_struct
源文件
https://docs.google.com/spreadsheets/d/1HpHV4VkFIhTiUB2P80l-LZ_9kPaLYTQd0DfEhXxcGno/edit#gid=659512552

./genschema.sh cns_struct v2.3 schema


### cns_temporal
源文件
https://docs.google.com/spreadsheets/d/1dH0ekNWX-HAfvEik088l4EMnLSRZ4AhQBZnqW4yv054/edit

./genschema.sh cns_temporal v2.3 schema


### cns_place
源文件
https://docs.google.com/spreadsheets/d/1aX-_QOj2GQALx-k_dJU-ak5LyvV0iIBaAg6s2N0UNmw/edit

./genschema.sh cns_place v2.3 schema


### cns_person
源文件
https://docs.google.com/spreadsheets/d/1b5DubotKUTU5tvT2pGXztwLpP63Xrc1le-VOuGKqbcw/edit

./genschema.sh cns_person v2.3 schema

### cns_organization
源文件
https://docs.google.com/spreadsheets/d/1qVaBhsbf0RRkrVhG0kkkn79q_fH4s4bV3oO5isGrX8o/edit

./genschema.sh cns_organization v2.3 schema




~~~~~~~
other files

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


### cns_law
源文件
https://docs.google.com/spreadsheets/d/1IL4GMyyXpoPM3bQfq3EFg_1kBZM3DLLz_gUycYXLvKM/edit#gid=659512552
./genschema.sh cns_law v1.1

### cns_ckyc
源文件
https://docs.google.com/spreadsheets/d/1ZXfIsxcNL5dJ16gpDOYWiqTdn3DIOWGVNrmcG8f5Md8/edit#gid=2126084884
./genschema.sh cns_ckyc v1.1

### test data on neo4j@Mac

#1. DOWNLOAD two CSV files from the excel
https://docs.google.com/spreadsheets/d/1qVaBhsbf0RRkrVhG0kkkn79q_fH4s4bV3oO5isGrX8o/edit#gid=659512552
sample_entity
sample_link

#2. CD neo4j directory
cd ~/my-software/neo4j-community-3.1.7

#3. REMOVE EXISTING DATA
mkdir data/cns_test
rm -rf data/databases/graph.db

#4. MOVE FILE
rm data/cns_test/*
mv ~/Downloads/cns_*sample_*csv data/cns_test/

#5. LOAD EXAMPLE DATA
bin/neo4j-admin import --nodes "data/cns_test/cns_organization\ -\ sample_entity.csv" --relationships "data/cns_test/cns_organization\ -\ sample_link.csv"

#6. restart neo4j
bin/neo4j restart

#7. open web browser, may need to one more page refresh to load db
http://localhost:7474/browser/
