import { apiClient } from "./client";

export async function listOffers({ limit = 20, offset = 0, pays, metier_code, q } = {}) {
  const { data } = await apiClient.get("/offers", {
    params: { limit, offset, pays, metier_code, q },
  });
  return data;
}

export async function getOffer(offerId) {
  const { data } = await apiClient.get(`/offers/${offerId}`);
  return data;
}
