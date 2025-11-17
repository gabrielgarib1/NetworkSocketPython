import os

# Cria um arquivo de 5MB com texto repetido
filename = 'test_file.txt'
# 20MB (limite do usuário)
# size_in_mb = 20 
# 5MB (para um teste mais rápido)
size_in_mb = 20
size_in_bytes = size_in_mb * 1024 * 1024

# Conteúdo
content = """Ingredientes\n \n

    1 porção de macarrão cabelinho de anjo (ou outro de cozimento rápido)\n
    1 xícara de água quente\n
    Temperinhos naturais a gosto (sal, pimenta, ervas secas ou frescas)\n
    1 colher de sopa de requeijão ou creme de castanhas\n\n

Modo de preparo\n\n

    Coloque o macarrão cabelinho de anjo em uma caneca ou tigela e cubra com a água quente.\n
    Se perceber que o macarrão não ficou bem cozido, coloque a caneca por alguns segundos no micro-ondas.\n
    Tempere com os condimentos de sua preferência.\n
    Finalize misturando o requeijão ou o creme de castanhas até ficar cremoso.\n
    Sirva imediatamente.\n
. \n"""

content_bytes = content.encode('utf-8')
content_len = len(content_bytes)

print(f"Criando arquivo '{filename}' com {size_in_mb}MB...")

with open(filename, 'wb') as f:
    for i in range(size_in_bytes // content_len):
        f.write(content_bytes)

print(f"Arquivo '{filename}' criado com {os.path.getsize(filename)} bytes.")