

## cnSchema 201806

### cns_top
源文件
https://docs.google.com/spreadsheets/d/1YKtEpHqa2I8LvuNAVDg3uwV6G9b4ZrNJsZdvPMS3_98/edit#gid=175537852

```
# 【人工】要求先下载Excel版本
# 【指令】移动文件
mv ~/Downloads/cns_top.xlsx ~/haizhi/git/kgtool/local/
# 【指令】更新Schema正式在线版本(jsonld)
python cns/cns_excel.py task_excel2jsonld --input_file=local/cns_top.xlsx --output_file=schema/cns_top.jsonld --debug_dir=local/
#【指令】生成Schema的DOT文件
python cns/cns_schema.py task_graphviz --input_file=schema/cns_top.jsonld --debug_dir=local/
#【指令】DOT文件生成图片
dot -Tpng local/cns_top_compact.dot -olocal/cns_top.png
'''

### cns_schemaorg
源文件
https://docs.google.com/spreadsheets/d/1mpiBxI5rK_qs86IpbXgN1xbhrxS_VYF0XjI_fcRpl00/edit#gid=364353024

```
# 【人工】要求先下载Excel版本
# 【指令】移动文件
mv ~/Downloads/schemaorg_translate.xlsx ~/haizhi/git/kgtool/local/
# 合并翻译文件和Schema.org对应的版本定义，生成Excel Schema定义
python cns/cns_schemaorg.py task_make_cns_schemaorg --version=3.4 --url_base=https://raw.githubusercontent.com/schemaorg/schemaorg/v3.4-release
# 【指令】更新Schema正式在线版本(jsonld)  
python cns/cns_excel.py task_excel2jsonld --input_file=local/cns_schemaorg.xls --output_file=schema/cns_schemaorg.jsonld --debug_dir=local/
#【指令】生成Schema的DOT文件
python cns/cns_schema.py task_graphviz --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
#【指令】DOT文件生成图片
dot -Tpng local/cns_schemaorg_compact.dot -olocal/cns_schemaorg.png
'''
TODO: super class/property 这一块还没有做
TODO: 形成template
TODO: 处理 domain/range


### cns_organization
源文件
https://docs.google.com/spreadsheets/d/1qVaBhsbf0RRkrVhG0kkkn79q_fH4s4bV3oO5isGrX8o/edit#gid=659512552

```
# 【人工】要求先下载Excel版本
# 【指令】移动文件
mv ~/Downloads/cns_organization.xlsx ~/haizhi/git/kgtool/local/
# 【指令】更新Schema正式在线版本(jsonld)  
python cns/cns_excel.py task_excel2jsonld --input_file=local/cns_organization.xlsx --output_file=schema/cns_organization.jsonld --debug_dir=local/
#【指令】生成Schema的DOT文件
python cns/cns_schema.py task_graphviz --input_file=schema/cns_organization.jsonld --debug_dir=local/
#【指令】DOT文件生成图片
dot -Tpng local/cns_organization_compact.dot -olocal/cns_organization.png
'''
