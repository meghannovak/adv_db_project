from transformers import pipeline
import csv
import os

out = open('../build/csvfiles/emotions.csv', 'a')
writer = csv.writer(out)

n = 1664
max_length = 512
for i in range(1613, n+1):
    file_path = f'../data/new_captions/{i}.txt'
    if os.path.exists(file_path):

        with open(file_path) as file:
            text = file.read()
            if len(text) == 0:
                row = [i,0,0,0,0,0,0,0]
                writer.writerow(row)
                continue
            if len(text) > max_length:
                text = text[:max_length]

            # run emotions model
            classifier = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=7)
            emotions = classifier(text)
            totals = {'neutral': 0, 'anger': 0, 'disgust': 0, 'fear': 0, 'joy': 0, 'sadness': 0, 'surprise': 0}
            for e in emotions:
                for s in e:
                    totals[s['label']] += s['score']
            # id, neutral, anger, disgust, fear, joy, sadness, suprise
            row = list(totals.values())
            row.insert(0, i)
            #row = [i, totals['neutral'], totals['anger'], totals['disgust'], totals['fear'], totals['joy'], totals['sadness'], totals['surprise']]
            writer.writerow(row)
            print(i)
    else:
        print("ERROR:", i)
