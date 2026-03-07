# Патч для загрузки Natasha (pymorphy2 требует pkg_resources)
import sys
try:
    import setuptools._vendor.pkg_resources as _pr
    sys.modules["pkg_resources"] = _pr
except Exception:
    pass
