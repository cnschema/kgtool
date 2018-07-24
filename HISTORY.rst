.. :changelog:

History
-------
0.0.5 (2018-07-13)
++++++++++++++++++
* change stats.py stat_table, reduce unique_counter's memory cost
* todo skip validate _Enum class validation
* change  cns_organization change property names
* change  cns_schema  add lambda_key_cns_link for cns_link;
* change  cns_schema  skip generate alternateName when it is the same as name
* add stat_kg_summary summarize list of entity and relation and validate 

0.0.4 (2018-07-03)
++++++++++++++++++
* change stat  add "_value_" in stat entry
* add core.parseListValue
* add cns_excel, cns_schema for process excel based CnSchema
* cns_excel.task_excel2jsonld  convert excel-based schema to JSON-LD version
* cns_schema with three main function cnsConvert, cnsValidate, cnsGraphviz

0.0.3 (2018-04-14)
++++++++++++++++++
* improve performance of stat

0.0.2 (2018-03-07)
++++++++++++++++++
* add core.any2sha256
* add table

0.0.1 (2018-03-07)
++++++++++++++++++
* migrate simple scripts from cnschema/cdata
* add kg.py to
  * stat_jsonld  count triples
  * stat_kg_pattern, count kg specific patterns
