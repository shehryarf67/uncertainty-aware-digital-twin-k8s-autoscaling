"""Convert the backed-up manuscript without changing its measured old results."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent
out=ROOT/'paper';out.mkdir(exist_ok=True)
with zipfile.ZipFile(ROOT/'overleaf-before.zip') as z:s=z.read('main_article.tex').decode()
(out/'main_article_before_20261114.tex.bak').write_text(s,encoding='utf8',newline='\n')
s=s.replace(r'\documentclass[11pt,a4paper]{article}',r'\documentclass[10pt,twocolumn,a4paper]{article}')
s=s.replace(r'\usepackage[margin=25mm]{geometry}',r'\usepackage[margin=18mm,columnsep=6mm]{geometry}')
s=s.replace(r'\usepackage{xurl}',r'\usepackage{xurl,graphicx}'+ '\n'+r'\setlength{\emergencystretch}{1em}')
s=s.replace(r'\begin{document}\maketitle',r'\begin{document}\twocolumn[\begin{@twocolumnfalse}\maketitle')
s=s.replace(r'\end{abstract}',r'\end{abstract}\vspace{4mm}\end{@twocolumnfalse}]',1)
s=s.replace(r'\begin{table}[htbp]',r'\begin{table*}[t]').replace(r'\end{table}',r'\end{table*}')
# Replica trajectories use a wide vector plot; the architecture fits one column.
s=s.replace(r'\begin{figure}[htbp]\centering\begin{tikzpicture}[x=1pt,y=1pt',r'\begin{figure*}[t]\centering\begin{tikzpicture}[x=1pt,y=1pt')
s=s.replace(r'\label{fig:trajectory}\end{figure}',r'\label{fig:trajectory}\end{figure*}')
s=s.replace(r'\begin{tikzpicture}[font=\small]',r'\resizebox{\columnwidth}{!}{\begin{tikzpicture}[font=\small]')
s=s.replace('\\end{tikzpicture}\n\\caption{Implemented feedback loop.','\\end{tikzpicture}}\n\\caption{Implemented feedback loop.')
s=s.replace(r'\date{October 2026}',r'\date{November 2026}')
assert s.count(r'\begin{table*}')==6 and s.count(r'\begin{figure*}')==1
(out/'main_article.tex').write_text(s,encoding='utf8',newline='\n')
print(out/'main_article.tex')
