#!/bin/bash

echo 'run after_install.sh: '

source new-venv/bin/activate 

echo 'cd /home/ubuntu/growbal-ai-repo/Growbal'
cd /home/ubuntu/growbal-ai-repo/Growbal

echo 'pip install -r requirements.txt' 

pip install -r requirements.txt

#npx prisma generate

#npx tsc