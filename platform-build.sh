#!/bin/bash
list=`echo $1| awk '{split($0,Ip,",")} END{for (var in Ip) print Ip[var];}'`

for platform in $list
 do
#   echo "$platform"
  echo "docker buildx build --pull --load --builder sage --platform ${platform} -t $2."

 done

