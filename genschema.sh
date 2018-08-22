#!/bin/bash
schemaName=$1
version=$2

# ./genschema.sh schema cns_top
# ./genschema.sh local cns_kg4ai

echo #schemaName
if [ "$schemaName" = "cns_top" ] || [ "$schemaName" = "cns_place" ] || [ "$schemaName" = "cns_schemaorg" ]  || [ "$schemaName" = "cns_person" ]  || [ "$schemaName" = "cns_organization" ]; then
  schemaDir=schema
else
  schemaDir=local/schema
fi

echo $schemaName
echo $schemaDir
#exit;

# 【人工】要求先下载Excel版本
# 【指令】移动文件
mv ~/Downloads/"$schemaName".xlsx local/debug/
# 【指令】更新Schema正式在线版本(jsonld)
python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/"$schemaName".xlsx --output_file="$schemaDir/$schemaName".jsonld --debug_dir=local/debug/
#python cns/cns_excel.py task_excel2jsonld --input_file=local/cns_top.xlsx --output_file=schema/cns_top.jsonld --debug_dir=local/debug/
#【指令】生成Schema的DOT文件
python kgtool/cns_graphviz.py task_graphviz --input_file="$schemaDir/$schemaName".jsonld  --dir_schema=schema --debug_dir=local/debug/
#【指令】DOT文件生成图片
dot -Tpng local/debug/"$schemaName"_compact.dot -olocal/image/"$schemaName".png
#【指令】DOT文件生成图片(包含依赖schema)
dot -Tpng local/debug/"$schemaName"_import.dot -olocal/image/"$schemaName"_import.png
