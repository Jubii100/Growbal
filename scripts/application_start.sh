#!/bin/bash

echo 'run application_start.sh: ' #>> /home/ubuntu/snack-mate-backend/deploy.log

cd /home/ubuntu/growbal-ai-repo/Growbal

echo 'pm2 restart node-app-change' #>> /home/ubuntu/snack-mate-backend/deploy.log
#pm2 restart 0 --update-env #>> /home/ubuntu/snack-mate-backend/deploy.log

sudo systemctl restart medai.service

#pm2 save