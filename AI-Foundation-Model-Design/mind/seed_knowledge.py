"""
seed_knowledge  —  Vio's built-in starter knowledge (so it isn't blank on day one).

Vio never hallucinates: it only says what it can verify or retrieve. That means an
empty Vio answers "I don't know" to everything, which feels useless at first. So we
seed it with a curated set of ACCURATE, general facts across science, geography,
the body, space, and technology. From the first launch Vio can already answer common
questions AND has enough text to reason over and generate from.

These are plain facts (encyclopaedia-level, uncontroversial). You extend Vio by
teaching it your own documents (📄 / teach:) — your knowledge sits alongside this.
"""

SEED = [
    # --- the human body ---
    "The heart pumps blood through the body. It has four chambers: two atria on top "
    "and two ventricles below. The left ventricle is the strongest chamber because it "
    "pushes oxygen-rich blood to the whole body. Blood carries oxygen and nutrients to "
    "every cell and removes waste like carbon dioxide.",
    "The lungs let the body take in oxygen and release carbon dioxide. Air travels down "
    "the windpipe into millions of tiny sacs called alveoli, where oxygen passes into the "
    "blood. An adult breathes about 12 to 20 times per minute at rest.",
    "The brain is the control centre of the body. It has around 86 billion neurons that "
    "communicate using electrical and chemical signals. Neurons that fire together "
    "strengthen their connections, which is how the brain learns and forms memories.",
    "Mitochondria are the powerhouse of the cell: they turn food and oxygen into usable "
    "energy called ATP. DNA is the molecule that stores genetic instructions, written in "
    "four bases: A, T, G, and C.",
    "The human skeleton has 206 bones in adults. Bones support the body, protect organs, "
    "and produce blood cells in their marrow. The smallest bone is the stapes in the ear.",

    # --- physical science ---
    "The water cycle describes how water moves on Earth. Water evaporates from oceans and "
    "lakes into the air. As the vapour rises it cools and condenses into clouds. When the "
    "droplets grow heavy they fall as rain or snow, called precipitation, then flow through "
    "rivers back to the sea, and the cycle repeats.",
    "Photosynthesis is how green plants make food. Using sunlight, they combine carbon "
    "dioxide from the air and water from the soil to produce glucose (sugar) and release "
    "oxygen. This is the source of almost all the oxygen we breathe.",
    "Matter exists mainly in three states: solid, liquid, and gas. Adding heat can melt a "
    "solid into a liquid and boil a liquid into a gas; removing heat reverses this. Water "
    "freezes at 0 degrees Celsius and boils at 100 degrees Celsius at sea level.",
    "Gravity is the force that pulls objects with mass toward each other. It keeps planets "
    "orbiting the Sun and gives us weight. On Earth, objects accelerate downward at about "
    "9.8 metres per second squared.",
    "The speed of light in a vacuum is about 299,792 kilometres per second, the fastest "
    "speed anything can travel. Sound travels far slower, about 343 metres per second in "
    "air, which is why we see lightning before we hear thunder.",
    "An atom is the basic building block of matter. It has a nucleus of protons and "
    "neutrons, surrounded by electrons. The number of protons decides which element it is; "
    "hydrogen has one proton and is the lightest and most common element in the universe.",

    # --- space ---
    "The Solar System has eight planets orbiting the Sun: Mercury, Venus, Earth, Mars, "
    "Jupiter, Saturn, Uranus, and Neptune. Jupiter is the largest planet and Mercury is "
    "the smallest and closest to the Sun.",
    "The Sun is a star, a giant ball of hot gas that produces energy by nuclear fusion, "
    "fusing hydrogen into helium in its core. It contains about 99.8 percent of all the "
    "mass in the Solar System.",
    "The Moon is Earth's only natural satellite. Its gravity causes the ocean tides, and "
    "it takes about 27 days to orbit the Earth. The Moon has no atmosphere, so its sky is "
    "always black and footprints left there can last for millions of years.",
    "Earth is the third planet from the Sun and the only known place with life. It is "
    "about 71 percent covered by water, has one moon, and takes 365.25 days to orbit the "
    "Sun, which is why we add a leap day every four years.",

    # --- geography ---
    "The Nile is the longest river in the world, about 6,650 kilometres, flowing north "
    "through north-east Africa into the Mediterranean Sea. The Amazon in South America "
    "carries the most water of any river.",
    "Mount Everest, on the border of Nepal and China, is the highest mountain above sea "
    "level at about 8,849 metres. The deepest part of the ocean is the Mariana Trench in "
    "the Pacific, nearly 11 kilometres deep.",
    "Earth has seven continents: Asia, Africa, North America, South America, Antarctica, "
    "Europe, and Australia. Asia is the largest and most populated. The four oceans are "
    "the Pacific, Atlantic, Indian, and Arctic; the Pacific is the largest.",
    "The Sahara is the largest hot desert in the world, covering much of North Africa. "
    "Deserts are defined by very low rainfall, not by heat, so Antarctica is technically "
    "the largest desert of all.",

    # --- technology & maths ---
    "A computer stores and processes information as bits, which are 0s and 1s. Eight bits "
    "make one byte. The CPU carries out instructions, RAM holds data in use, and storage "
    "like an SSD keeps data when the power is off.",
    "The internet is a global network of connected computers that communicate using shared "
    "rules called protocols. The World Wide Web is a service built on top of it, made of "
    "linked pages you view in a browser.",
    "A prime number is a whole number greater than 1 that has exactly two divisors: 1 and "
    "itself. The first primes are 2, 3, 5, 7, 11, and 13. Two is the only even prime.",
    "Artificial intelligence is software that performs tasks that normally need human "
    "intelligence, such as understanding language or recognising images. Machine learning "
    "is AI that improves by finding patterns in data rather than being programmed with "
    "fixed rules.",
]
