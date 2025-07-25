#!/bin/bash

echo 'run after_install.sh: '

echo 'cd /home/ubuntu/growbal-ai-repo/Growbal'
cd /home/ubuntu/growbal-ai-repo/Growbal

source new-venv/bin/activate 

echo 'pip install -r requirements.txt' 

pip install -r requirements.txt

#npx prisma generate

#npx tsc