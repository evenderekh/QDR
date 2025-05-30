# QDR
JSON data consumed by the Qumran Digital Reader (https://qumran.dev)

# Schema
```jsonc
[                           // Open the Dead Sea Scrolls (Biblical or Non-Biblical)
  {                         // Open the first scroll
    "scroll": "2Q29",       // Scroll name
    "fragments": [          // Open the list of fragments
      [                     // Open the first fragment (a list of lines)
        [                   // Open the first line (a list of word blocks)
          [                 // Open the first word block (5 items):
            "ב",            // Surface form (no damage marks)
            "[ ב",          // Surface form (full)
            "בְּ",            // Lemma
            "ptcl",         // Morphology
            "Num 23:5"      // Biblical verse or fragment number
          ]
        ]
      ]
    ]
  }
]
