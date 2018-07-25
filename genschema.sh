#!/bin/bash
schemaName=$1

# ./genschema.sh schema cns_top
# ./genschema.sh local cns_kg4ai

echo #schemaName
if [ "$schemaName" = "cns_top" ] || [ "$schemaName" = "cns_creativework" ] || [ "$schemaName" = "cns_place" ] || [ "$schemaName" = "cns_schemaorg" ]  || [ "$schemaName" = "cns_person" ]  || [ "$schemaName" = "cns_organization" ]; then
  schemaDir=schema
else
  schemaDir=local
fi

echo $schemaName
echo $schemaDir
#exit;

# 【人工】要求先下载Excel版本
# 【指令】移动文件
mv ~/Downloads/"$schemaName".xlsx local/
# 【指令】更新Schema正式在线版本(jsonld)
python cns/cns_excel.py task_excel2jsonld --input_file=local/"$schemaName".xlsx --output_file="$schemaDir/$schemaName".jsonld --debug_dir=local/
#【指令】生成Schema的DOT文件
python kgtool/cns_schema.py task_graphviz --input_file="$schemaDir/$schemaName".jsonld --debug_dir=local/
#【指令】DOT文件生成图片
dot -Tpng local/"$schemaName"_compact.dot -olocal/"$schemaName".png
#【指令】DOT文件生成图片(包含依赖schema)
dot -Tpng local/"$schemaName"_import.dot -olocal/"$schemaName"_import.png
