#!/bin/bash

echo 'run application_start.sh: ' #>> /home/ubuntu/snack-mate-backend/deploy.log

cd /home/ubuntu/growbal-ai-repo/Growbal

echo 'restarting the apps' #>> /home/ubuntu/snack-mate-backend/deploy.log
#pm2 restart 0 --update-env #>> /home/ubuntu/snack-mate-backend/deploy.log

sudo systemctl restart growbal-ai-app.service
sudo systemctl restart django-app.service

#pm2 save