Get-ChildItem 'D:\Comfyui\python\Lib\site-packages\llama_cpp' | Select-Object -ExpandProperty Name
'---LIB---'
Get-ChildItem 'D:\Comfyui\python\Lib\site-packages\llama_cpp\lib' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
'---BIN---'
Get-ChildItem 'D:\Comfyui\python\Lib\site-packages\llama_cpp\bin' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
