# Nginx for MemOS Exchange Frontend
FROM nginx:alpine

# 复制自定义配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制前端文件
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
