import no_mans_sky_base_builder.part as part


class MESSAGEMODULE(part.Part):
    """Capture extra "Message" attribute."""
    @property
    def message(self):
        return self.object.get("Message", "")
    
    @message.setter
    def message(self, value):
        self.object["Message"] = str(value)

    def serialise(self):
        data = super(MESSAGEMODULE, self).serialise()
        data["Message"] = self.message
        return data
    
    @classmethod
    def deserialise_from_data(cls, data, *args, **kwargs):
        part = super(MESSAGEMODULE, cls).deserialise_from_data(data, *args, **kwargs)
        part.message = data.get("Message", "")
        return part