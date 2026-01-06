import astropy.coordinates as coord


class custom_coord(coord.SkyCoord):
    @property
    def prop(self):
        return self.random_attr


c = custom_coord('00h42m30s', '+41d12m00s', frame='icrs')
try:
    c.prop
except AttributeError as e:
    print(f"Error message: {e}")
    print(f"Error type: {type(e)}")