from functools import cached_property


class Cacheable:
    """Class with clear_cached method who clear all methods
    cached_property decorator
    """

    def clear_cache(self):
        """Clear all methods with cache_property decorator"""
        for attr_name in dir(self.__class__):
            class_attr = getattr(self.__class__, attr_name)
            if isinstance(class_attr, cached_property):
                if attr_name in self.__dict__:
                    del self.__dict__[attr_name]
