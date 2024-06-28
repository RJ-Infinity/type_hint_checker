# Type Hint Checker

a replacement for isinstance that works with type hints

exports `are_type_compatible` which can be used as a drop in replacement for isinstance
but works with type hints

```py
are_type_compatible([0, 1, 2], list[int]) # true
are_type_compatible([0, 1, "2"], list[int]) # false
```


also takes two optional arguments the context which would be the function or class the
type hint came from and the namespace which is the namespace to search for types
