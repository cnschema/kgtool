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
schemaRelease="$schemaName"_"$version"
echo $schemaRelease
#exit;

# 【人工】要求先下载Excel版本
# 【指令】移动文件
mv ~/Downloads/"$schemaName".xlsx local/debug/
# 【指令】更新Schema正式在线版本(jsonld)
python cns/cns_io.py task_excel2jsonld --input_file=local/debug/"$schemaName".xlsx --schema_dir=schema --output_dir="$schemaDir/" --debug_dir=local/debug/
#python cns/cns_io.py task_excel2jsonld --input_file=local/cns_top.xlsx --output_file=schema/cns_top.jsonld --debug_dir=local/debug/
#【指令】生成Schema的DOT文件
python kgtool/cns_graphviz.py task_graphviz --input_file="$schemaDir/$schemaRelease".jsonld  --schema_dir=schema --debug_dir=local/debug/
#【指令】DOT文件生成图片
dot -Tpng local/debug/"$schemaRelease"_compact.dot -olocal/image/"$schemaRelease".png
#【指令】DOT文件生成图片(包含依赖schema)
dot -Tpng local/debug/"$schemaRelease"_import.dot -olocal/image/"$schemaRelease"_import.png
#【指令】DOT文件生成图片(全图)
dot -Tpng local/debug/"$schemaRelease"_full.dot -olocal/image/"$schemaRelease"_full.png
