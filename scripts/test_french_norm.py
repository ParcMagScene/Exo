from tts.french_text_norm import normalize_fr

tests = [
    "M. Dupont a paye 1234,56 EUR le 1er janvier 2024.",
    "La SNCF annonce 25% de retards, mais aussi des trains supprimes.",
    "Mme Curie est nee en 1867 ; cf. Wikipedia, p.ex. l'article principal.",
    "Le prix : 9,99 euros pour le 2eme article.",
    "Il y a 3 enfants et 12 chiens.",
    "L'OTAN, la NASA, le FBI et l'API REST.",
]
for t in tests:
    print("IN :", t)
    print("OUT:", normalize_fr(t))
    print()
