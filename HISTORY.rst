.. :changelog:

History
-------
0.1.0 (2018-10-12)
++++++++++++++++++
* refactor code, switch back to lowercase&underscore code style, split cns_schema into cns_model, cns_validate, cns_convert, cns_graphviz
* remove cns_creativework
* refactor cns_item validation logic and code
* add run_normalize_item, covert property value by schema template definition
* add stat_json_path, count json object for jsonpath, values, unique values, samples and value distribution
* rewrite validation code, update validation report
* switch to new excel representation, support 4 sheets definition, template, changelog, metadata

0.0.6 (2018-07-25)
++++++++++++++++++
* move cns.cns_schema to kgtool.cns_schema to better external access

0.0.5 (2018-07-24)
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
* cns_schema with three main function cnsConvert, run_validate, run_graphviz

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
