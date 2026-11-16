---
tags: [generative-part]
max_turns: 80
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Tengo un brazo robótico pequeño impreso en PLA. Esta pieza es el antebrazo (forearm.stl, en mm): va atornillado al codo con un M3 en el origen y en la punta lleva el servo de la muñeca (wrist_servo.stl es su envolvente, ya colocado en el mismo sistema de ejes), sujeto con dos tornillitos a los postes. El servo pesa 9 g y la pinza con la carga unos 150 g, colgando a unos 45 mm más allá del servo. Quiero aligerar el antebrazo sin que pierda rigidez. ¿Puedes mejorarlo con diseño generativo?

Input files: forearm.stl, wrist_servo.stl, arm.py
