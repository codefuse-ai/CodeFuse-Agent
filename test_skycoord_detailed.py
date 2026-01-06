import astropy.coordinates as coord
import traceback


class custom_coord(coord.SkyCoord):
    @property
    def prop(self):
        return self.random_attr


def test_error():
    c = custom_coord('00h42m30s', '+41d12m00s', frame='icrs')
    try:
        c.prop
    except AttributeError as e:
        print("Full traceback:")
        traceback.print_exc()
        print(f"\nError message: {e}")
        return str(e)


if __name__ == "__main__":
    test_error()