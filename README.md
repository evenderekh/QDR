# QDR  
JSON data consumed by the [Qumran Digital Reader](https://qumran.dev)

# Schema  

## Biblical

```jsonc
[                           // Open the Dead Sea Scrolls (Biblical)
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
```

## Non-Biblical

```jsonc
[                           // Open the Dead Sea Scrolls (Non-Biblical)
  {                         // Open the first scroll
    "scroll": "CD",         // Scroll name
    "fragments": [          // Open the list of fragments
      [                     // Open the first fragment (a list of lines)
        [                   // Open the first line (a list of word blocks)
          [                 // Open the first word block (4 items):
            "ו",            // Surface form (no damage marks)
            "ו",            // Surface form (full)
            "וְ",            // Lemma  
            "ptcl"          // Morphology (particle)
          ]
        ]
      ]
    ]
  }
]
```

# License  
[CC-BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

# Source  
[The Dead Sea Scrolls in Text-Fabric](https://github.com/ETCBC/dss)
