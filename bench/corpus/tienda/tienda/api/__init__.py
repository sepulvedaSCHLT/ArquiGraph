"""Capa de entrada: valida la peticion, llama al dominio y responde.

No hay servidor. Un "recurso" es una funcion que recibe un diccionario
y devuelve ``(codigo, cuerpo)``, que es todo lo que hace falta para
probar la traduccion entre el exterior y el dominio.
"""
