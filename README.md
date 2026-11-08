# ktasom

CLI que recebe um link de vídeo do YouTube, ou um CSV com vários, e baixa o áudio em MP3.

## Requisitos

- Python 3.9 ou mais recente
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/), incluindo o `ffprobe`
- [deno](https://deno.com/), recomendado pelo yt-dlp para extrair vídeos do YouTube

```sh
pipx install "yt-dlp[default]"
sudo apt install ffmpeg
curl -fsSL https://deno.land/install.sh | sh
```

Mantenha o yt-dlp atualizado com `pipx upgrade yt-dlp`, porque versões antigas costumam parar de funcionar quando o YouTube muda.

O pacote snap do ffmpeg não serve, porque não expõe o `ffprobe` no PATH e não enxerga todas as pastas do sistema. Se ele estiver instalado, troque pelo do apt com `sudo snap remove ffmpeg`.

## Instalação

Crie o comando `ktasom`, rodando a partir da pasta do projeto:

```sh
ln -s "$PWD/ktasom.py" ~/.local/bin/ktasom
```

A pasta `~/.local/bin` precisa estar no PATH. O comando aponta para este arquivo, então não mova nem apague a pasta do projeto.

## Uso

```sh
ktasom "https://youtu.be/XXXXXXXXXXX"
ktasom links.csv
ktasom links.csv --output ~/Musicas
```

Coloque o link entre aspas, porque o shell interpreta caracteres como `?` e `&`.

Os MP3s vão para o diretório atual quando `--output` não é informado, e cada arquivo recebe o título do vídeo como nome.

## Formato do CSV

Os links podem estar em qualquer coluna, e tanto o cabeçalho quanto o separador (`,` ou `;`) são opcionais. Só o que for link do YouTube é aproveitado, e links repetidos são baixados uma vez.

```csv
https://www.youtube.com/watch?v=XXXXXXXXXXX
https://youtu.be/YYYYYYYYYYY
```

Não é preciso informar o nome da música, porque o arquivo recebe o título do vídeo. Outras colunas do CSV são ignoradas.

## Comportamento

- Um link com falha não interrompe os demais. No fim, os links que falharam são listados e o comando sai com código 1.
- Rodar de novo só baixa o que falta. Os vídeos concluídos ficam registrados em `.baixados.txt`, dentro da pasta de destino. Apague esse arquivo para baixar tudo outra vez.
- Um link de vídeo que também tem `list=` baixa só o vídeo. Um link que aponta direto para uma playlist baixa a playlist inteira.

## Testes

```sh
python3 -m unittest
```

Os testes usam um `yt-dlp` falso e não acessam a rede.

## Direitos autorais

Baixe apenas conteúdo que você tem direito de usar. Os termos de serviço do YouTube e a lei de direitos autorais continuam valendo para o uso desta ferramenta.
