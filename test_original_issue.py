#!/usr/bin/env python3
"""
Test to reproduce the original issue described where
subclassed SkyCoord gives misleading attribute access message
"""

import astropy
import astropy.coordinates as coord


class custom_coord(coord.SkyCoord):
    @property
    def prop(self):
        return self.random_attr


def main():
    print("Testing SkyCoord subclass attribute access issue...")
    print(f"Astropy version: {coord.__version__}")
    
    c = custom_coord('00h42m30s', '+41d12m00s', frame='icrs')
    
    try:
        result = c.prop
        print(f"Unexpected success: {result}")
    except AttributeError as e:
        print(f"AttributeError: {e}")
        # Check if the error message is misleading
        error_str = str(e)
        if "'custom_coord' object has no attribute 'prop'" in error_str:
            print("ISSUE REPRODUCED: Misleading error message!")
            print("Expected: should mention 'random_attr' not 'prop'")
        elif "'custom_coord' object has no attribute 'random_attr'" in error_str:
            print("No issue: Error message correctly identifies missing attribute")
        else:
            print(f"Unexpected error message: {error_str}")


if __name__ == "__main__":
    main()