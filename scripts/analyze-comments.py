from transformers import pipeline
import csv
import os
import numpy
from transformers import TFBertForSequenceClassification


out = open('../build/csvfiles/comments.csv', 'a')
writer = csv.writer(out)

n = 1664
max_length = 512

classifier = pipeline('sentiment-analysis', model="ProsusAI/finbert", tokenizer="ProsusAI/finbert")

for i in range(n+1):
    file_path = f'../data/comments/{i}.txt'
    if os.path.exists(file_path):
        with open(file_path) as file:
            text = file.read()
            if len(text) > max_length:
                text = text[:max_length]

            # run polarity model
            result = classifier(text, top_k=None)
            sorted_result = sorted(result, key=lambda x: x['label'])
            scores = [entry['score'] for entry in sorted_result]
            scores.insert(0, i)
            writer.writerow(scores)
            
    else:
        print("ERROR:", i)

