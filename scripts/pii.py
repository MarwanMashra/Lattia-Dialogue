from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")

text = """
Harilala Rasoanaivo, un homme d'affaires local d'Antananarivo, a enregistré une nouvelle société nommée "Rasoanaivo Enterprises" au Lot II M 92 Antohomadinika. Son numéro est le +261 32 22 345 67, et son adresse électronique est harilala.rasoanaivo@telma.mg. Il a fourni son numéro de sécu 501-02-1234 pour l'enregistrement.
"""

labels = [
    "work",
    "booking number",
    "personally identifiable information",
    "driver licence",
    "person",
    "book",
    "full address",
    "company",
    "actor",
    "character",
    "email",
    "passport number",
    "Social Security Number",
    "phone number",
]
entities = model.predict_entities(text, labels)

for entity in entities:
    print(entity["text"], "=>", entity["label"])
